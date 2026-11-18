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
    def __init__(self, log_file):
        self.lock = threading.RLock()
        self.proc = None
        self.log_file = log_file

    @property
    def alive(self):
        return self.proc is not None and self.proc.poll() is None

    def ensure(self):
        with self.lock:
            if self.alive:
                return
            t = time.time()
            logf = open(self.log_file, "ab")
            self.proc = subprocess.Popen([sys.executable, WORKER], stdin=subprocess.PIPE,
                                         stdout=subprocess.PIPE, stderr=logf)
            logf.close()
            line = self.proc.stdout.readline()
            if line.strip() != b"READY":
                self.stop()
                raise RuntimeError("speech engine failed to start (see the log)")
            log.info("engine loaded in %.1fs", time.time() - t)

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
            log.info("engine unloaded")
