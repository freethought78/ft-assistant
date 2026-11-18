#!/usr/bin/env python3
"""Push-to-talk dictation: hold a mouse button, speak, release -> text is typed
into whatever window has focus (X11 only).

This process is lightweight: it only watches for the button. The heavy Whisper
engine (whisper_worker.py) and the microphone are started on the first press and
shut down after IDLE_SEC without use, so nothing sits on the GPU while idle."""

import collections
import fcntl
import json
import logging
import os
import re
import struct
import subprocess
import sys
import threading
import time
import queue

import numpy as np
import sounddevice as sd
from Xlib import X, display
from Xlib.ext import record
from Xlib.protocol import rq

# ---------------- settings ----------------
HOME = os.path.dirname(os.path.abspath(__file__))
TRIGGER_BUTTON = int(os.environ.get("DICTATE_BUTTON", 12))  # X11 mouse button number
IDLE_SEC = float(os.environ.get("DICTATE_IDLE_SEC", 0))  # unload engine after this; 0 = right after each dictation
SAMPLE_RATE = 16000
PREROLL_SEC = 0.3          # audio kept from just before the press (while mic is open)
MIN_SEC = 0.35             # ignore taps shorter than this
MIN_RMS = 0.002            # ignore near-silent recordings
BEEPS = True
WORKER = os.path.join(HOME, "whisper_worker.py")
LOG_FILE = os.path.join(HOME, "dictation.log")
# Phrases Whisper tends to invent on silence/noise; dropped if they are the whole result.
HALLUCINATIONS = {"thank you.", "thank you", "thanks for watching!", "thanks for watching.",
                  "you", "you.", "bye.", "bye!", "thank you very much.", ".", "okay."}
# Subtitle credits Whisper tacks onto the end of real speech (learned from video subtitles),
# e.g. "Closed Captioning by www.microsoft.com", "Subtitles by the Amara.org community".
# Only removed at the very end, and only when the credit word is capitalized, so a sentence
# like "the subtitles by default are off" is left alone.
CREDIT_RE = re.compile(
    r"[\s,]*\b(?:Closed [Cc]aption(?:ing|ed|s)?|Caption(?:ing|ed|s)?|Subtitles?|Subtitling"
    r"|Transcription|Transcribed)\b(?: [\w.'-]+){0,4}? by\b.{0,80}$")
# ------------------------------------------

logging.basicConfig(filename=LOG_FILE, level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("dictate")


def notify(msg):
    subprocess.Popen(["notify-send", "-a", "Dictation", "-t", "3000", "Dictation", msg],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def single_instance():
    lock = open(os.path.join(HOME, ".lock"), "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print("Dictation is already running.")
        sys.exit(0)
    return lock


def tone(freq, ms=70, vol=0.15, rate=48000):
    t = np.arange(int(rate * ms / 1000)) / rate
    env = np.minimum(1, np.minimum(t, t[::-1]) * 200)  # short fade in/out, no clicks
    return (vol * env * np.sin(2 * np.pi * freq * t)).astype(np.float32), rate


START_BEEP = tone(880)
STOP_BEEP = tone(587)


def beep(b):
    if BEEPS:
        try:
            sd.play(*b)
        except Exception:
            pass


class Recorder:
    """Mic is opened on demand. Audio is only kept in memory while the button is
    held (plus a short pre-roll while open). Nothing is written to disk."""

    def __init__(self):
        self.lock = threading.Lock()
        self.recording = False
        self.frames = []
        self.preroll = collections.deque(maxlen=int(PREROLL_SEC * SAMPLE_RATE / 512) + 1)
        self.stream = None

    @property
    def is_open(self):
        return self.stream is not None

    def open(self):
        self.close()
        self.preroll.clear()
        self.stream = sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32",
                                     blocksize=512, callback=self._cb)
        self.stream.start()
        log.info("mic opened")

    def close(self):
        if self.stream is not None:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception:
                pass
            self.stream = None
            log.info("mic closed")

    def _cb(self, data, frames, t, status):
        chunk = data[:, 0].copy()
        with self.lock:
            if self.recording:
                self.frames.append(chunk)
            else:
                self.preroll.append(chunk)

    def start(self):
        if self.stream is None or not self.stream.active:
            self.open()
        with self.lock:
            self.frames = list(self.preroll)
            self.recording = True

    def stop(self):
        with self.lock:
            self.recording = False
            frames, self.frames = self.frames, []
        return np.concatenate(frames) if frames else np.zeros(0, np.float32)


class Engine:
    """Owns the whisper_worker subprocess. Killing the process is what guarantees
    all GPU memory is returned."""

    def __init__(self):
        self.lock = threading.RLock()
        self.proc = None

    @property
    def alive(self):
        return self.proc is not None and self.proc.poll() is None

    def ensure(self):
        with self.lock:
            if self.alive:
                return
            t = time.time()
            logf = open(LOG_FILE, "ab")
            self.proc = subprocess.Popen([sys.executable, WORKER], stdin=subprocess.PIPE,
                                         stdout=subprocess.PIPE, stderr=logf)
            line = self.proc.stdout.readline()
            if line.strip() != b"READY":
                self.stop()
                raise RuntimeError("speech engine failed to start (see dictation.log)")
            log.info("engine loaded in %.1fs", time.time() - t)

    def warm(self):
        """Start loading in the background (called on button press)."""
        def go():
            try:
                self.ensure()
            except Exception as e:
                log.error("warm-up failed: %s", e)
        threading.Thread(target=go, daemon=True).start()

    def transcribe(self, audio):
        with self.lock:
            for attempt in (1, 2):
                try:
                    self.ensure()
                    data = audio.astype(np.float32).tobytes()
                    self.proc.stdin.write(struct.pack("<I", len(data)) + data)
                    self.proc.stdin.flush()
                    line = self.proc.stdout.readline()
                    if not line:
                        raise RuntimeError("speech engine exited")
                    reply = json.loads(line)
                    if "error" in reply:
                        raise RuntimeError(reply["error"])
                    return reply["text"]
                except (BrokenPipeError, RuntimeError, ValueError):
                    if attempt == 2:
                        raise
                    log.warning("engine problem, restarting it", exc_info=True)
                    self.stop()

    def stop(self):
        with self.lock:
            if self.proc is None:
                return
            p, self.proc = self.proc, None
            try:
                p.stdin.close()
                p.wait(timeout=5)
            except Exception:
                p.kill()
                p.wait()
            log.info("engine unloaded")


def clean_text(text):
    """Drop subtitle credits from the end; return "" if nothing real is left."""
    prev = None
    while text and text != prev:
        prev = text
        text = CREDIT_RE.sub("", text).strip()
    if text.lower() in HALLUCINATIONS:
        return ""
    return text


def type_text(text):
    subprocess.run(["xdotool", "type", "--clearmodifiers", "--delay", "4", "--", text])


def main():
    _lock = single_instance()
    rec = Recorder()
    engine = Engine()
    jobs = queue.Queue()
    ctl = threading.Lock()
    state = {"down": False, "last_used": time.time()}

    def worker():
        while True:
            audio = jobs.get()
            try:
                dur = len(audio) / SAMPLE_RATE
                rms = float(np.sqrt(np.mean(audio ** 2))) if len(audio) else 0.0
                if dur < MIN_SEC or rms < MIN_RMS:
                    log.info("skipped (dur=%.2fs rms=%.4f)", dur, rms)
                    continue
                t = time.time()
                text = engine.transcribe(audio)
                cleaned = clean_text(text)
                # The user's words are never logged, only sizes and timings.
                log.info("%.1fs audio -> %.2fs, %d chars%s", dur, time.time() - t, len(cleaned),
                         " (filtered %d chars)" % (len(text) - len(cleaned)) if cleaned != text else "")
                if cleaned:
                    type_text(cleaned + " ")
            except Exception as e:
                log.exception("transcription failed")
                notify(f"Error: {e}")
            finally:
                state["last_used"] = time.time()
                jobs.task_done()
                if IDLE_SEC <= 0:
                    release_if_idle()

    def release_if_idle():
        # Stops the tool's own mic stream and the engine. The system microphone
        # itself is never muted or changed.
        with ctl:
            busy = state["down"] or jobs.unfinished_tasks
            idle = time.time() - state["last_used"] >= IDLE_SEC
            if busy or not idle or not (engine.alive or rec.is_open):
                return
            log.info("idle, releasing resources")
            rec.close()
        engine.stop()

    def idle_watch():
        while True:
            time.sleep(10)
            release_if_idle()

    threading.Thread(target=worker, daemon=True).start()
    threading.Thread(target=idle_watch, daemon=True).start()

    def on_press():
        with ctl:
            if state["down"]:
                return
            state["down"] = True
            state["last_used"] = time.time()
            try:
                rec.start()
            except Exception as e:
                state["down"] = False
                log.exception("mic failed")
                notify(f"Microphone error: {e}")
                return
        engine.warm()          # loads while you talk, if it was unloaded
        beep(START_BEEP)       # beep = mic is live, start speaking

    def on_release():
        with ctl:
            if not state["down"]:
                return
            state["down"] = False
            state["last_used"] = time.time()
            audio = rec.stop()
        beep(STOP_BEEP)
        jobs.put(audio)

    rdpy = display.Display()
    ctx = rdpy.record_create_context(0, [record.AllClients], [{
        "core_requests": (0, 0), "core_replies": (0, 0),
        "ext_requests": (0, 0, 0, 0), "ext_replies": (0, 0, 0, 0),
        "delivered_events": (0, 0),
        "device_events": (X.ButtonPress, X.ButtonRelease),
        "errors": (0, 0), "client_started": False, "client_died": False,
    }])

    def callback(reply):
        if reply.category != record.FromServer or reply.client_swapped:
            return
        data = reply.data
        while data:
            ev, data = rq.EventField(None).parse_binary_value(data, rdpy.display, None, None)
            if ev.detail != TRIGGER_BUTTON:
                continue
            if ev.type == X.ButtonPress:
                on_press()
            elif ev.type == X.ButtonRelease:
                on_release()

    log.info("ready: hold mouse button %d to dictate (engine unloads after %ds idle)",
             TRIGGER_BUTTON, IDLE_SEC)
    print("Dictation ready.")
    rdpy.record_enable_context(ctx, callback)  # blocks forever


if __name__ == "__main__":
    main()
