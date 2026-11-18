"""Microphone recording and beeps.

The mic stream is the tool's own input stream: it is opened on demand and closed when idle.
The system microphone itself is never muted, disabled or reconfigured.
Audio is only kept in memory and never written to disk."""

import collections
import logging
import threading

import numpy as np
import sounddevice as sd

SAMPLE_RATE = 16000
PREROLL_SEC = 0.3          # audio kept from just before the press (while the stream is open)

log = logging.getLogger("ft_assistant")


def tone(freq, ms=70, vol=0.15, rate=48000):
    t = np.arange(int(rate * ms / 1000)) / rate
    env = np.minimum(1, np.minimum(t, t[::-1]) * 200)  # short fade in/out, no clicks
    return (vol * env * np.sin(2 * np.pi * freq * t)).astype(np.float32), rate


START_BEEP = tone(880)     # mic is live, start speaking
STOP_BEEP = tone(587)      # release registered


def beep(b):
    try:
        sd.play(*b)
    except Exception:
        pass


class Recorder:
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
        log.info("mic stream opened")

    def close(self):
        if self.stream is not None:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception:
                pass
            self.stream = None
            log.info("mic stream closed")

    def _cb(self, data, frames, t, status):
        chunk = data[:, 0].copy()
        with self.lock:
            (self.frames if self.recording else self.preroll).append(chunk)

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
