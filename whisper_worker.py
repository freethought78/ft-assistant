#!/usr/bin/env python3
"""Speech-to-text worker. Started on demand by dictate.py and stopped when idle,
so the GPU memory it uses is fully released between dictation sessions.

Protocol (stdin/stdout): prints READY once loaded; then for each request reads
a 4-byte little-endian length + float32 16 kHz mono audio, and replies with one
JSON line {"text": ...}. Exits when stdin closes."""

import json
import os
import struct
import sys

# Keep the real stdout for the protocol; anything libraries print goes to stderr (the log).
proto_out = os.fdopen(os.dup(1), "wb")
os.dup2(2, 1)

import numpy as np
from faster_whisper import WhisperModel

HOME = os.path.dirname(os.path.abspath(__file__))
MODEL = os.environ.get("DICTATE_MODEL", "large-v3-turbo")
VOCAB_FILE = os.path.join(HOME, "vocabulary.txt")


def load_vocab():
    try:
        with open(VOCAB_FILE) as f:
            words = [w.strip() for w in f if w.strip() and not w.startswith("#")]
        return ", ".join(words) or None
    except FileNotFoundError:
        return None


model = WhisperModel(MODEL, device="cuda", compute_type="float16",
                     download_root=os.path.join(HOME, "models"))
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
