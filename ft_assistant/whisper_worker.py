#!/usr/bin/env python3
"""Speech-to-text worker. Started on demand by the app and stopped right after each dictation,
so the GPU memory it uses is fully released.

Protocol (stdin/stdout): prints READY once loaded; then for each request reads a 4-byte
little-endian length + float32 16 kHz mono audio, and replies with one JSON line
{"text": ...} or {"error": ...}. Exits when stdin closes.

If the graphics card can't be used (for example its NVIDIA driver is too old for the speech
engine), the same model is loaded on the processor instead: then the first line is "READY cpu"
and replies carry "device": "cpu", so the app can say so and skip the card next time.

Environment:
  FT_ASSISTANT_MODEL       Whisper model name (default large-v3-turbo)
  FT_ASSISTANT_DEVICE      cuda | cpu (default cuda)
  FT_ASSISTANT_MODELS_DIR  where the model files live
  FT_ASSISTANT_VOCAB       vocabulary file (one word per line, # comments)"""

import json
import os
import struct
import sys

import procname          # this script's own folder is on the search path

procname.set_name("speech")

# Keep the real stdout for the protocol; anything libraries print goes to stderr (the log).
proto_out = os.fdopen(os.dup(1), "wb")
os.dup2(2, 1)

import numpy as np  # noqa: E402
from faster_whisper import WhisperModel  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ft_assistant import config  # noqa: E402
from ft_assistant.textproc import build_hotwords  # noqa: E402

MODEL = os.environ.get("FT_ASSISTANT_MODEL", "large-v3-turbo")
DEVICE = os.environ.get("FT_ASSISTANT_DEVICE", "cuda")
MODELS_DIR = os.environ.get("FT_ASSISTANT_MODELS_DIR") or None
VOCAB_FILE = os.environ.get("FT_ASSISTANT_VOCAB", "")


def load_vocab():
    """Hint words for Whisper: the keyword hints plus the user's vocabulary file (re-read for
    every dictation, so edits apply at once)."""
    try:
        with open(VOCAB_FILE, encoding="utf-8") as f:
            words = [w.strip() for w in f if w.strip() and not w.startswith("#")]
    except OSError:
        words = []
    return build_hotwords(words, config.load().keyword)      # re-read: setup may change it


def load_model(device):
    return WhisperModel(MODEL, device=device, compute_type="float16" if device == "cuda" else "int8",
                        download_root=MODELS_DIR)


def use_processor(e):
    """Switch to the processor after the graphics card failed (`e`). Noted in the log."""
    global model, device
    sys.stderr.write(f"Warning: the graphics card can't be used ({e}); using the processor.\n")
    sys.stderr.flush()
    device = "cpu"
    model = load_model(device)


device = DEVICE
try:
    model = load_model(device)
except Exception as e:
    if device != "cuda":
        raise
    use_processor(e)
proto_out.write(b"READY\n" if device == DEVICE else b"READY cpu\n")
proto_out.flush()

inp = sys.stdin.buffer
while True:
    hdr = inp.read(4)
    if len(hdr) < 4:
        break
    (n,) = struct.unpack("<I", hdr)
    audio = np.frombuffer(inp.read(n), dtype=np.float32)
    reply = None
    for attempt in (1, 2):
        try:
            segs, _ = model.transcribe(audio, language="en", beam_size=5, vad_filter=True,
                                       condition_on_previous_text=False, hotwords=load_vocab())
            reply = {"text": " ".join(s.text.strip() for s in segs).strip()}
            break
        except Exception as e:
            # Some graphics-card problems (a missing cuBLAS/cuDNN library) only show up here.
            if attempt == 1 and device == "cuda":
                try:
                    use_processor(e)
                    continue
                except Exception as e2:
                    e = e2
            reply = {"error": str(e)}
            break
    if device != DEVICE:
        reply["device"] = device
    proto_out.write((json.dumps(reply) + "\n").encode())
    proto_out.flush()
