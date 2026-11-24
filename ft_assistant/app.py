"""Main process: hold the Assistant key, speak, release.

- Normal dictation is typed into the focused window.
- "Assistant, <request>" goes to the chosen code agent (Claude Code or OpenCode) in a visible
  terminal window, or straight into the agent's terminal if you're already typing in one.
- "Assistant setup" opens the setup screen.
- "Assistant new topic" starts a new conversation (also by itself after a quiet gap).
- "Assistant undo" removes the dictation just typed, if nothing was typed or clicked since.

What the user says is never written to the log; only sizes and timings are."""

import logging
import logging.handlers
import os
import queue
import subprocess
import sys
import threading
import time

import numpy as np

from . import agent_windows, buildinfo, config, harness, open_setup, procname, textproc, updater
from . import plat
from .audio import SAMPLE_RATE, START_BEEP, STOP_BEEP, Recorder, beep
from .engine import Engine
from .setup_ui import CHANGED as SETUP_CHANGED

MIN_SEC = 0.35             # ignore taps shorter than this
MIN_RMS = 0.002            # ignore near-silent recordings
OPENED_WINDOW_WAIT = 8.0   # seconds to watch for the terminal window we just opened
NEW_CONVERSATION_WAIT = 1.5   # after /clear or /new, before typing the request
TITLE_WAIT = 20.0          # and then for its assistant to set the window title

log = logging.getLogger("ft_assistant")


def setup_logging():
    d = config.config_dir()
    d.mkdir(parents=True, exist_ok=True)
    log_file = d / "ft-assistant.log"
    # Errors and warnings only, plus one start-up line: no record of when or how much anyone
    # dictates (user decision, 2026-11-18). What was said is never logged at any level.
    # Activity lines exist at debug level for development and are never written to the file.
    handler = logging.handlers.RotatingFileHandler(log_file, maxBytes=200_000, backupCount=1,
                                                   encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    root = logging.getLogger()
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    return log_file


def single_instance():
    lock = plat.lock_single_instance(config.config_dir() / ".lock")
    if lock is None:
        print("FT Assistant is already running.")
        raise SystemExit(0)
    return lock


class App:
    def __init__(self, settings, log_file):
        self.settings = settings
        self.rec = Recorder()
        self.engine = Engine(log_file, on_processor=self.processor_notice)
        self.jobs = queue.Queue()
        self.ctl = threading.Lock()
        self.down = False
        # The agent's window survives FT Assistant's own restarts (an update): remembered for
        # the login session, see agent_windows.py.
        self.window_file = agent_windows.state_file()
        self.login = plat.login_session()
        self.windows_lock = threading.Lock()
        self.agent_window = agent_windows.load(self.window_file, self.login)
        # harness key -> its most recent window we opened
        self.our_windows = set(self.agent_window.values())  # terminal windows we opened for one
        # Windows that showed their assistant's title (and every remembered one): they must
        # still show it to count as ours, since window numbers get reused (gnome-terminal gives
        # a new window the number of one just closed).
        self.titled = set(self.our_windows)
        self.setup_proc = None          # the setup screen, while it's open
        self.commands_proc = None       # the voice commands window ("<word> help")
        self.listener = None            # the current Assistant key listener
        # The last dictation typed, for "<word> undo": (window, how many characters, the input
        # count then). Its length only, never its text; forgotten after an undo or any command.
        self.last_typed = None
        self.caps_trigger = (settings.trigger.get("type") == "key"
                             and settings.trigger.get("keysym") == "Caps_Lock")

    # ---- key handling (called from the listener thread)

    def on_press(self):
        with self.ctl:
            if self.down or self.setup_proc is not None:   # paused while setup is open
                return
            self.down = True
            try:
                self.rec.start()
            except Exception as e:
                self.down = False
                log.exception("mic failed")
                plat.notify(f"Microphone error: {e}")
                return
        self.engine.warm()
        beep(START_BEEP)

    def on_release(self):
        with self.ctl:
            if not self.down:
                return
            self.down = False
            audio = self.rec.stop()
        if self.caps_trigger:
            plat.caps_lock_off()        # Caps Lock is never left on
        beep(STOP_BEEP)
        # Remember where the user was when they let go; that decides where text goes.
        self.jobs.put((audio, plat.active_window()))

    # ---- processing (worker thread)

    def worker(self):
        while True:
            audio, focus = self.jobs.get()
            try:
                self.process(audio, focus)
            except Exception as e:
                log.exception("processing failed")
                plat.notify(f"Error: {e}")
            finally:
                self.jobs.task_done()
                self.release_resources()

    def process(self, audio, focus):
        dur = len(audio) / SAMPLE_RATE
        rms = float(np.sqrt(np.mean(audio ** 2))) if len(audio) else 0.0
        if dur < MIN_SEC or rms < MIN_RMS:
            log.debug("skipped (dur=%.2fs rms=%.4f)", dur, rms)
            return
        t = time.time()
        raw = self.engine.transcribe(audio)
        text = textproc.clean_text(raw)
        cmd = textproc.route(text, self.settings.dictation_only, self.settings.keyword)
        log.debug("%.1fs audio -> %.2fs, %s, %d chars", dur, time.time() - t, cmd.kind, len(cmd.text))
        if self.caps_trigger:
            plat.caps_lock_off()
        if cmd.kind == "undo":
            self.undo(focus)
            return
        self.last_typed = None
        if cmd.kind == "dictate":
            if cmd.text:
                typed = cmd.text + " "
                plat.type_text(typed)
                if focus[0] is not None:
                    self.last_typed = (focus[0], len(typed), plat.input_count())
        elif cmd.kind == "setup":
            self.open_setup()
        elif cmd.kind == "help":
            self.open_commands()
        elif cmd.kind == "stop":
            self.stop_assistant(focus)
        elif cmd.kind == "new_topic":
            self.run_assistant(cmd.text, focus, new=True)
        else:
            self.run_assistant(cmd.text, focus)

    def undo(self, focus):
        """ "<word> undo": Backspace over the last dictation, only if it's surely still the last
        thing in that window: the same window has focus and the user hasn't typed or clicked
        since. Otherwise nothing is deleted."""
        last, self.last_typed = self.last_typed, None
        if last is None:
            plat.notify("Nothing to undo.")
            return
        wid, length, count = last
        if focus[0] != wid or plat.input_count() != count:
            plat.notify("Nothing was undone: you've typed or clicked since.")
            return
        if not plat.input_watch_ok():     # can't tell whether anything was typed: delete nothing
            plat.notify("Nothing was undone: FT Assistant couldn't check for typing or clicks.")
            return
        plat.press_backspace(length)
        log.debug("undid the last dictation")

    def in_harness(self, focus):
        wid, cls, title = focus
        if wid is None:
            return False
        if wid in self.our_windows and self._still_ours(wid, title):
            return True
        return plat.is_terminal_class(cls) and harness.harness_from_title(title) is not None

    def _still_ours(self, wid, title, key=None):
        """Is a window we opened still that assistant's window (not a reused window number)?"""
        shown = harness.harness_from_title(title)
        if shown is not None and (key is None or shown == key):
            self.titled.add(wid)
            return True
        return wid not in self.titled

    def agent_window_for(self, key):
        """The open window we opened for this harness, or None (then forgotten)."""
        wid = self.agent_window.get(key)
        if wid is None:
            return None
        if wid in plat.terminal_windows() and self._still_ours(wid, plat.window_title(wid), key):
            return wid
        self._forget(wid)
        return None

    def _forget(self, wid):
        with self.windows_lock:
            self.our_windows.discard(wid)
            self.titled.discard(wid)
            for k in [k for k, w in self.agent_window.items() if w == wid]:
                del self.agent_window[k]
            agent_windows.save(self.window_file, self.login, dict(self.agent_window))

    def focused_harness(self, focus):
        """Which assistant the focused assistant window is (in_harness(focus) is true)."""
        wid, _cls, title = focus
        return harness.harness_from_title(title) or next(
            (k for k, w in self.agent_window.items() if w == wid), None) or self.settings.harness

    def quiet_too_long(self, key):
        """Has the current conversation had no activity for the quiet gap? Then "<word>, ..."
        from elsewhere starts a new one (the agent's own work counts as activity)."""
        gap = self.settings.quiet_gap_minutes
        if not gap:
            return False
        last = harness.last_activity(key, config.sessions_dir())
        return last is not None and time.time() - last > gap * 60

    def new_conversation_here(self, key):
        """Start a new conversation in the focused assistant window: /clear (Claude Code) or /new
        (OpenCode). The old conversation stays saved."""
        plat.type_text(harness.NEW_CONVERSATION[key])
        time.sleep(0.3)                  # let the command menu settle before Enter
        plat.press_enter()
        time.sleep(NEW_CONVERSATION_WAIT)

    def run_assistant(self, text, focus, new=False):
        """ "<word>, <text>": to the assistant. new: in a new conversation ("<word> new topic")."""
        if self.in_harness(focus):       # dictating in its window: always that conversation
            if new:
                self.new_conversation_here(self.focused_harness(focus))
            if text:
                plat.type_text(text)
                plat.press_enter()
            return
        self.settings = config.load()          # pick up changes made in the setup screen
        if not self.settings.uses_assistant:
            plat.notify("No assistant chosen yet. Hold the Assistant key and say "
                        f"\"{self.settings.keyword} setup\".")
            return
        key = self.settings.harness
        if text and not new and self.quiet_too_long(key):
            new = True
            log.debug("quiet gap passed: new %s conversation", key)
        # One ongoing conversation: if its window is still open, bring it forward and send there.
        wid = self.agent_window_for(key)
        if wid is not None and plat.activate_window(wid):
            if new:
                self.new_conversation_here(key)
            if text:
                plat.type_text(text)
                plat.press_enter()
            log.debug("sent to the open %s window", key)
            return
        before = plat.terminal_windows()
        folder = config.sessions_dir()
        running = plat.processes_in(folder) if folder.is_dir() else set()
        h, proc = harness.open_session(key, text, new=new)
        log.debug("opened %s window", h.key)
        threading.Thread(target=self._remember_new_window,
                         args=(key, before, (folder, running, proc)), daemon=True).start()

    def _remember_new_window(self, key, before, started=None):
        end = time.time() + OPENED_WINDOW_WAIT
        while time.time() < end:
            time.sleep(0.3)
            now = plat.terminal_windows()
            new = now - before
            if new:
                wid = max(new)
                with self.windows_lock:
                    self.our_windows = (self.our_windows & now) | new   # forget closed windows
                    self.titled &= now
                    self.agent_window[key] = wid
                    agent_windows.save(self.window_file, self.login, dict(self.agent_window))
                self._watch_title(wid, key)
                return
        if started and not self._agent_started(*started):
            # Nothing happened (the 0.3.0 bug did this): say so instead of staying silent.
            log.error("the %s window didn't open", key)
            plat.notify(f"Couldn't open {harness.HARNESSES[key].name}'s window.")

    @staticmethod
    def _agent_started(folder, running_before, proc):
        """No new window appeared: did the agent start anyway (in a new tab of an open terminal
        window, say)? A new process in the sessions folder (Linux), or the started process still
        running (Windows: the agent itself; xterm and the like: the terminal)."""
        now = plat.processes_in(folder)
        if now is not None and running_before is not None and now - running_before:
            return True
        return proc is not None and proc.poll() is None

    def _watch_title(self, wid, key):
        """Note when the new window shows its assistant's title (see self.titled)."""
        end = time.time() + TITLE_WAIT
        while time.time() < end and wid in plat.terminal_windows():
            if harness.harness_from_title(plat.window_title(wid)) == key:
                self.titled.add(wid)
                return
            time.sleep(0.5)

    # Escape presses that interrupt each assistant's current work. OpenCode wants a second one
    # ("esc again to interrupt", within a few seconds; tested 2026-11-21). Claude Code stops on
    # the first, and a second would open its "rewind" menu.
    STOP_PRESSES = {"claude": 1, "opencode": 2}

    def stop_assistant(self, focus):
        """ "<word> stop": interrupt the assistant's current work, as Escape in its window does.
        The assistant window being dictated to, or else the one FT Assistant opened (brought to
        the front)."""
        if self.in_harness(focus):           # Escape goes to the focused window
            wid = focus[0]
            key = self.focused_harness(focus)
        else:
            self.settings = config.load()
            key = self.settings.harness
            wid = self.agent_window_for(key)
            if wid is None or not plat.activate_window(wid):
                plat.notify("No assistant window is open to stop.")
                return
        for i in range(self.STOP_PRESSES.get(key, 1)):
            if i:
                time.sleep(0.3)
            plat.press_escape()
        log.debug("interrupted the %s window", key)

    def open_commands(self):
        """ "<word> help": the voice commands window, in its own process."""
        if self.commands_proc is not None and self.commands_proc.poll() is None:
            return
        self.commands_proc = subprocess.Popen([procname.executable("help"), "-m",
                                               "ft_assistant.voice_commands"])

    def open_setup(self):
        """Show the setup screen in its own process; the Assistant key is paused meanwhile."""
        if self.setup_proc is not None:
            return
        argv, env = open_setup.command()
        self.setup_proc = subprocess.Popen(argv, env=env)
        threading.Thread(target=self._wait_setup, daemon=True).start()

    def _wait_setup(self):
        code = self.setup_proc.wait()
        old_trigger = self.settings.trigger
        self.settings = config.load()
        self.caps_trigger = (self.settings.trigger.get("type") == "key"
                             and self.settings.trigger.get("keysym") == "Caps_Lock")
        self.setup_proc = None
        if code == SETUP_CHANGED and self.settings.trigger != old_trigger and self.listener:
            # Switch keys in place: stop watching the old key; main() starts the new one.
            log.debug("Assistant key changed; switching to it")
            self.listener.stop()

    # ---- update check (background thread)

    def busy(self):
        return self.down or self.jobs.unfinished_tasks or self.setup_proc is not None

    def update_loop(self):
        """About a minute after start, then hourly: if a day has passed since the last check,
        check GitHub (never during a dictation) and notify about a newer version."""
        time.sleep(float(os.environ.get("FT_ASSISTANT_UPDATE_DELAY", 60)))
        tick = float(os.environ.get("FT_ASSISTANT_UPDATE_TICK", 3600))
        while True:
            try:
                while self.busy():
                    time.sleep(30)
                if updater.due_for_check(updater.load_state()):
                    rel = updater.check()
                    state = updater.load_state()
                    if updater.should_notify(rel, state):
                        updater.mark_notified(state, rel.version)
                        updater.save_state(state)
                        log.debug("update available: %s", rel.version)
                        plat.notify_with_action(
                            f"FT Assistant {rel.version} is available. Click to see what's new, "
                            f"or say \"{self.settings.keyword} setup\".", "Show", self.open_setup)
            except Exception:
                log.exception("update check failed")
            time.sleep(tick)

    def processor_notice(self):
        """Shown once when the graphics card couldn't be used and the processor took over."""
        plat.notify("Your graphics card couldn't be used for speech (its NVIDIA driver may be too "
                    "old), so FT Assistant is using the processor instead. It works, just more "
                    "slowly. To make it fast again, update the NVIDIA driver and restart the "
                    "computer.")

    def release_resources(self):
        """Close the tool's own mic stream and stop the engine right after each dictation.
        The system microphone itself is never muted or changed."""
        with self.ctl:
            if self.down or self.jobs.unfinished_tasks:
                return
            self.rec.close()
        self.engine.stop()


def main():
    procname.set_name("app")
    log_file = setup_logging()
    _lock = single_instance()  # noqa: F841 (held for the life of the process)
    problem = plat.session_problem()
    if problem:
        log.error(problem)
        plat.notify(problem)
        raise SystemExit(1)
    # The speech worker reads these (the vocabulary file is re-read on every dictation).
    os.environ.setdefault("FT_ASSISTANT_VOCAB", str(config.config_dir() / "vocabulary.txt"))
    os.environ.setdefault("FT_ASSISTANT_MODELS_DIR", str(config.data_dir() / "models"))
    os.environ.setdefault("HF_HUB_OFFLINE", "1")      # the model is downloaded at setup only
    settings = config.load()
    app = App(settings, log_file)
    threading.Thread(target=app.worker, daemon=True).start()
    threading.Thread(target=app.update_loop, daemon=True).start()
    trig = settings.trigger
    log.info("ready: version %s, Assistant key %s, harness %s", buildinfo.describe(),
             trig.get("keysym") or f"mouse button {trig.get('button')}",
             "dictation only" if settings.dictation_only else (settings.harness or "(not chosen)"))
    print("FT Assistant ready.")
    if not settings.harness_chosen:
        app.open_setup()            # first run: choose an assistant before anything else
    while True:                     # a new listener whenever the Assistant key is changed
        app.listener = plat.TriggerListener(trig, app.on_press, app.on_release)
        app.listener.run()          # blocks until the key changes
        trig = app.settings.trigger
        log.debug("ready: Assistant key %s", trig.get("keysym") or f"mouse button {trig.get('button')}")
