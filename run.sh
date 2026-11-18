#!/bin/bash
# Launcher: points the GPU libraries at the copies installed inside the venv.
D="$(dirname "$(readlink -f "$0")")"
SP=$("$D/venv/bin/python" -c "import site;print(site.getsitepackages()[0])")
export LD_LIBRARY_PATH="$SP/nvidia/cublas/lib:$SP/nvidia/cudnn/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export HF_HUB_OFFLINE=1   # model is already downloaded; never phone home
exec "$D/venv/bin/python" "$D/dictate.py" "$@"
