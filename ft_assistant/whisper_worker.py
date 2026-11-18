#!/usr/bin/env python3
"""Speech-to-text worker. Started on demand by the app and stopped right after each dictation,
so the GPU memory it uses is fully released.

Protocol (stdin/stdout): prints READY once loaded; then for each request reads a 4-byte
little-endian length + float32 16 kHz mono audio, and replies with one JSON line
{"text": ...} or {"error": ...}. Exits when stdin closes.

Environment:
  FT_ASSISTANT_MODEL       Whisper model name (default large-v3-turbo)
  FT_ASSISTANT_DEVICE      cuda | cpu (default cuda)
  FT_ASSISTANT_MODELS_DIR  where the model files live
  FT_ASSISTANT_VOCAB       vocabulary file (one word per line, # comments)"""

import json
import os
import struct
import sys

# Keep the real stdout for the protocol; anything libraries print goes to stderr (the log).
proto_out = os.fdopen(os.dup(1), "wb")
os.dup2(2, 1)

import numpy as np  # noqa: E402
from faster_whisper import WhisperModel  # noqa: E402

MODEL = os.environ.get("FT_ASSISTANT_MODEL", "large-v3-turbo")
DEVICE = os.environ.get("FT_ASSISTANT_DEVICE", "cuda")
MODELS_DIR = os.environ.get("FT_ASSISTANT_MODELS_DIR") or None
VOCAB_FILE = os.environ.get("FT_ASSISTANT_VOCAB", "")


def load_vocab():
    try:
        with open(VOCAB_FILE, encoding="utf-8") as f:
            words = [w.strip() for w in f if w.strip() and not w.startswith("#")]
        return ", ".join(words) or None
    except OSError:
        return None


model = WhisperModel(MODEL, device=DEVICE, compute_type="float16" if DEVICE == "cuda" else "int8",
                     download_root=MODELS_DIR)
proto_out.write(b"READY\n")
proto_out.flush()

inp = sys.stdin.buffer
while True:
    hdr = inp.read(4)
    if len(hdr) < 4:
        break
    (n,) = struct.unpack("<I", hdr)
    audio = np.frombuffer(inp.read(n), dtype=np.float32)
    try:
        segs, _ = model.transcribe(audio, language="en", beam_size=5, vad_filter=True,
                                   condition_on_previous_text=False, hotwords=load_vocab())
        reply = {"text": " ".join(s.text.strip() for s in segs).strip()}
    except Exception as e:
        reply = {"error": str(e)}
    proto_out.write((json.dumps(reply) + "\n").encode())
    proto_out.flush()
