import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

try:
    import numpy as np
    from ft_assistant import engine
except ImportError:          # numpy missing: the engine can't run here
    engine = None

# A pretend speech worker: says READY (plus " cpu" if the card "failed") and answers every
# request, noting which device it was told to use.
FAKE_WORKER = r'''
import json, os, struct, sys
out = sys.stdout.buffer
dev = os.environ.get("FT_ASSISTANT_DEVICE", "cuda")
fail = os.environ.get("FAKE_CARD_FAILS") == "1" and dev == "cuda"
out.write(b"READY cpu\n" if fail else b"READY\n"); out.flush()
while True:
    hdr = sys.stdin.buffer.read(4)
    if len(hdr) < 4:
        break
    sys.stdin.buffer.read(struct.unpack("<I", hdr)[0])
    reply = {"text": "started on " + dev}
    if fail:
        reply["device"] = "cpu"
    out.write((json.dumps(reply) + "\n").encode()); out.flush()
'''


@unittest.skipIf(engine is None, "numpy isn't installed")
class ProcessorFallback(unittest.TestCase):
    def run_engine(self, card_fails):
        with tempfile.TemporaryDirectory() as t:
            worker = Path(t, "worker.py")
            worker.write_text(FAKE_WORKER)
            notices = []
            with mock.patch.object(engine, "WORKER", str(worker)), \
                    mock.patch.dict(os.environ, {"FAKE_CARD_FAILS": "1" if card_fails else "0",
                                                 "FT_ASSISTANT_DEVICE": "cuda"}):
                e = engine.Engine(Path(t, "log"), on_processor=lambda: notices.append(1))
                audio = np.zeros(1600, np.float32)
                first = e.transcribe(audio)
                e.stop()
                second = e.transcribe(audio)       # a new worker, like the next dictation
                e.stop()
            return first, second, e.processor_only, notices

    def test_card_works(self):
        self.assertEqual(self.run_engine(False),
                         ("started on cuda", "started on cuda", False, []))

    def test_card_fails_once_then_processor_directly(self):
        first, second, processor_only, notices = self.run_engine(True)
        self.assertTrue(processor_only)
        self.assertEqual(notices, [1])                    # told once, not every dictation
        self.assertEqual(second, "started on cpu")        # skips the card from then on


if __name__ == "__main__":
    unittest.main()
