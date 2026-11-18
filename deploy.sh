#!/bin/bash
# Deploy the dictation tool from this repo to the live install.
#
#   ./deploy.sh              dry run: show what differs between repo and live (changes nothing)
#   ./deploy.sh --yes        back up the live files, then copy the repo versions over
#   ./deploy.sh --rollback   restore the most recent backup
#
# Never restarts the tool. dictate.py / whisper_worker.py / run.sh changes need a restart
# (see CLAUDE.md); vocabulary.txt is re-read on every transcription, so it applies at once.
set -euo pipefail

REPO="$(dirname "$(readlink -f "$0")")"
LIVE="$HOME/.local/share/voice-dictation"
BACKUPS="$LIVE/backups"
PY="$LIVE/venv/bin/python"

# repo path -> live path
declare -A MAP=(
  [dictate.py]="$LIVE/dictate.py"
  [whisper_worker.py]="$LIVE/whisper_worker.py"
  [run.sh]="$LIVE/run.sh"
  [vocabulary.txt]="$LIVE/vocabulary.txt"
  [autostart/voice-dictation.desktop]="$HOME/.config/autostart/voice-dictation.desktop"
)
RESTART_FILES="dictate.py whisper_worker.py run.sh"

changed=()
for f in "${!MAP[@]}"; do
  if ! cmp -s "$REPO/$f" "${MAP[$f]}"; then changed+=("$f"); fi
done

if [[ "${1:-}" == "--rollback" ]]; then
  last=$(ls -1d "$BACKUPS"/*/ 2>/dev/null | sort | tail -n 1)
  [[ -n "$last" ]] || { echo "No backups in $BACKUPS"; exit 1; }
  for f in "${!MAP[@]}"; do
    [[ -e "$last/$f" ]] && cp -p "$last/$f" "${MAP[$f]}" && echo "restored $f"
  done
  echo "Rolled back to $last (restart the tool if code changed)."
  exit 0
fi

if [[ ${#changed[@]} -eq 0 ]]; then
  echo "Live install already matches the repo."
  exit 0
fi

echo "Files that differ (repo -> live):"
for f in "${changed[@]}"; do
  echo "== $f"
  diff -u "${MAP[$f]}" "$REPO/$f" --label "live/$f" --label "repo/$f" || true
done

if [[ "${1:-}" != "--yes" ]]; then
  echo
  echo "Dry run only. Re-run with --yes to deploy."
  exit 0
fi

# Only committed code from main may go live; the redesign lives on `next` until it's merged.
branch=$(git -C "$REPO" symbolic-ref --short HEAD 2>/dev/null || echo "(detached)")
if [[ "$branch" != "main" ]]; then
  echo "Refusing to deploy: on branch '$branch'. Only main deploys to the live tool."
  exit 1
fi
if [[ -n "$(git -C "$REPO" status --porcelain)" ]]; then
  echo "Refusing to deploy: uncommitted changes. Commit them to main first."
  exit 1
fi

# Refuse to deploy Python that doesn't compile.
for f in dictate.py whisper_worker.py; do
  "$PY" -c "import ast,sys; ast.parse(open(sys.argv[1]).read(), sys.argv[1])" "$REPO/$f"
done
bash -n "$REPO/run.sh"

stamp=$(date +%Y%m%d-%H%M%S)
mkdir -p "$BACKUPS/$stamp/autostart"
for f in "${!MAP[@]}"; do
  [[ -e "${MAP[$f]}" ]] && cp -p "${MAP[$f]}" "$BACKUPS/$stamp/$f"
done
for f in "${changed[@]}"; do
  cp -p "$REPO/$f" "${MAP[$f]}"
  echo "deployed $f"
done
echo "Backup of previous live files: $BACKUPS/$stamp"

for f in "${changed[@]}"; do
  if [[ " $RESTART_FILES " == *" $f "* ]]; then
    echo "Code changed: restart the tool to pick it up."
    break
  fi
done
