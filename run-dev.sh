#!/bin/bash
# Run the development build from this repo, alongside the installed FT Assistant, without touching it.
# - Reuses the install's Python environment, Whisper model and word list (read-only).
# - Keeps its own settings and log in ~/.config/ft-assistant-dev/.
# - Uses its own Assistant key (from that settings file), so it doesn't clash with the installed
#   copy's key.
# - Its own data folder too, so its setup screen never offers to update or uninstall the
#   installed copy.
# run-branch.sh uses this script too: FT_DEV_SOURCE (the code to run), FT_DEV_CONFIG_DIR and
# FT_DEV_DATA_DIR (its own folders). Inherited FT_ASSISTANT_* folders are never used.
REPO="${FT_DEV_SOURCE:-$(dirname "$(readlink -f "$0")")}"
LIVE="${XDG_DATA_HOME:-$HOME/.local/share}/ft-assistant"
PY="$LIVE/python/bin/python3"
[ -x "$PY" ] || { echo "FT Assistant isn't installed in $LIVE (run-dev.sh borrows its Python)." >&2; exit 1; }
SP=$("$PY" -c "import site;print(site.getsitepackages()[0])")
export LD_LIBRARY_PATH="$SP/nvidia/cublas/lib:$SP/nvidia/cudnn/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export HF_HUB_OFFLINE=1
export PYTHONNOUSERSITE=1
export FT_ASSISTANT_CONFIG_DIR="${FT_DEV_CONFIG_DIR:-$HOME/.config/ft-assistant-dev}"
export FT_ASSISTANT_DATA_DIR="${FT_DEV_DATA_DIR:-$HOME/.local/share/ft-assistant-dev}"
export FT_ASSISTANT_MODELS_DIR="$LIVE/models"
export FT_ASSISTANT_MODEL="${FT_ASSISTANT_MODEL:-$LIVE/models/large-v3-turbo}"
export FT_ASSISTANT_DEVICE="${FT_ASSISTANT_DEVICE:-cuda}"
export FT_ASSISTANT_VOCAB="${XDG_CONFIG_HOME:-$HOME/.config}/ft-assistant/vocabulary.txt"
export PYTHONPATH="$REPO${PYTHONPATH:+:$PYTHONPATH}"
exec "$PY" -m ft_assistant "$@"
