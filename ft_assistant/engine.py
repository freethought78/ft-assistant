"""Owns the Whisper worker subprocess. Killing the process is what guarantees all GPU memory
is returned, so the engine is stopped right after each dictation."""

import json
import logging
import os
import struct
import subprocess
import sys
import threading
import time

import numpy as np

log = logging.getLogger("ft_assistant")
WORKER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "whisper_worker.py")


class Engine:
    def __init__(self, log_file, on_processor=None):
        self.lock = threading.RLock()
        self.proc = None
        self.log_file = log_file
        # Set once the graphics card has failed: until FT Assistant restarts, the engine goes
        # straight to the processor instead of trying the card on every dictation.
        self.processor_only = False
        self.on_processor = on_processor      # called once when that happens

    def _switched_to_processor(self):
        if self.processor_only:
            return
        self.processor_only = True
        log.warning("graphics card can't be used; using the processor until the next restart")
        if self.on_processor:
            try:
                self.on_processor()
            except Exception:
                log.exception("processor notice failed")

    @property
    def alive(self):
        return self.proc is not None and self.proc.poll() is None

    def ensure(self):
        with self.lock:
            if self.alive:
                return
            t = time.time()
            logf = open(self.log_file, "ab")
            extra = {"creationflags": 0x08000000} if sys.platform == "win32" else {}  # no console
            if self.processor_only:
                extra["env"] = dict(os.environ, FT_ASSISTANT_DEVICE="cpu")
            self.proc = subprocess.Popen([sys.executable, WORKER], stdin=subprocess.PIPE,
                                         stdout=subprocess.PIPE, stderr=logf, **extra)
            logf.close()
            words = self.proc.stdout.readline().split()
            if not words or words[0] != b"READY":
                self.stop()
                raise RuntimeError("speech engine failed to start (see the log)")
            if b"cpu" in words[1:]:
                self._switched_to_processor()
            log.debug("engine loaded in %.1fs", time.time() - t)

    def warm(self):
        """Start loading in the background (called on key press)."""
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
                    if reply.get("device") == "cpu":
                        self._switched_to_processor()
                    if "error" in reply:
                        raise RuntimeError(reply["error"])
                    return reply["text"]
                except (BrokenPipeError, RuntimeError, ValueError):
                    if attempt == 2:
                        raise
                    log.warning("engine problem, restarting it")
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
            log.debug("engine unloaded")
