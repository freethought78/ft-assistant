"""Main process: hold the Assistant key, speak, release.

- Normal dictation is typed into the focused window.
- "Assistant, <request>" goes to the chosen code agent (Claude Code or OpenCode) in a visible
  terminal window, or straight into the agent's terminal if you're already typing in one.
- "Assistant setup" opens the setup screen.

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

from . import __version__, config, harness, open_setup, textproc, updater
from . import plat
from .audio import SAMPLE_RATE, START_BEEP, STOP_BEEP, Recorder, beep
from .engine import Engine
from .setup_ui import CHANGED as SETUP_CHANGED

MIN_SEC = 0.35             # ignore taps shorter than this
MIN_RMS = 0.002            # ignore near-silent recordings
OPENED_WINDOW_WAIT = 8.0   # seconds to watch for the terminal window we just opened

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
        self.engine = Engine(log_file)
        self.jobs = queue.Queue()
        self.ctl = threading.Lock()
        self.down = False
        self.our_windows = set()        # terminal windows this tool opened for an agent
        self.agent_window = {}          # harness key -> its most recent window we opened
        self.setup_proc = None          # the setup screen, while it's open
        self.listener = None            # the current Assistant key listener
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
        cmd = textproc.route(text, self.settings.dictation_only)
        log.debug("%.1fs audio -> %.2fs, %s, %d chars", dur, time.time() - t, cmd.kind, len(cmd.text))
        if self.caps_trigger:
            plat.caps_lock_off()
        if cmd.kind == "dictate":
            if cmd.text:
                plat.type_text(cmd.text + " ")
        elif cmd.kind == "setup":
            self.open_setup()
        else:
            self.run_assistant(cmd.text, focus)

    def in_harness(self, focus):
        wid, cls, title = focus
        if wid is None:
            return False
        if wid in self.our_windows:
            return True
        return plat.is_terminal_class(cls) and harness.harness_from_title(title) is not None

    def run_assistant(self, text, focus):
        if self.in_harness(focus):
            if text:
                plat.type_text(text)
                plat.press_enter()
            return
        self.settings = config.load()          # pick up changes made in the setup screen
        if not self.settings.uses_assistant:
            plat.notify("No assistant chosen yet. Hold the Assistant key and say "
                        "\"Assistant setup\".")
            return
        key = self.settings.harness
        # One ongoing conversation: if its window is still open, bring it forward and send there.
        wid = self.agent_window.get(key)
        if wid is not None and wid in plat.terminal_windows() and plat.activate_window(wid):
            if text:
                plat.type_text(text)
                plat.press_enter()
            log.debug("sent to the open %s window", key)
            return
        before = plat.terminal_windows()
        h = harness.open_session(key, text)
        log.debug("opened %s window", h.key)
        threading.Thread(target=self._remember_new_window, args=(key, before), daemon=True).start()

    def _remember_new_window(self, key, before):
        end = time.time() + OPENED_WINDOW_WAIT
        while time.time() < end:
            time.sleep(0.3)
            now = plat.terminal_windows()
            new = now - before
            if new:
                self.our_windows = (self.our_windows & now) | new   # forget closed windows
                self.agent_window[key] = max(new)
                return

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
                            "or say \"Assistant setup\".", "Show", self.open_setup)
            except Exception:
                log.exception("update check failed")
            time.sleep(tick)

    def release_resources(self):
        """Close the tool's own mic stream and stop the engine right after each dictation.
        The system microphone itself is never muted or changed."""
        with self.ctl:
            if self.down or self.jobs.unfinished_tasks:
                return
            self.rec.close()
        self.engine.stop()


def main():
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
    log.info("ready: version %s, Assistant key %s, harness %s", __version__,
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
