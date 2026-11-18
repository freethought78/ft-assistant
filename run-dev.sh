#!/bin/bash
# Run the development build from this repo, alongside the live tool, without touching it.
# - Reuses the live install's Python environment and Whisper model (read-only).
# - Keeps its own settings and log in ~/.config/ft-assistant-dev/.
# - Uses its own Assistant key (from that settings file), so it doesn't clash with the live
#   tool's mouse button 12.
REPO="$(dirname "$(readlink -f "$0")")"
LIVE="$HOME/.local/share/voice-dictation"
SP=$("$LIVE/venv/bin/python" -c "import site;print(site.getsitepackages()[0])")
export LD_LIBRARY_PATH="$SP/nvidia/cublas/lib:$SP/nvidia/cudnn/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export HF_HUB_OFFLINE=1
export FT_ASSISTANT_CONFIG_DIR="$HOME/.config/ft-assistant-dev"
export FT_ASSISTANT_MODELS_DIR="$LIVE/models"
export FT_ASSISTANT_VOCAB="$LIVE/vocabulary.txt"
export PYTHONPATH="$REPO${PYTHONPATH:+:$PYTHONPATH}"
exec "$LIVE/venv/bin/python" -m ft_assistant "$@"
