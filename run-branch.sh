#!/bin/bash
# Run a branch of this repo IN PLACE OF the installed FT Assistant, and switch back.
# Only one copy ever runs, on the user's normal Assistant key.
#
#   ./run-branch.sh <branch>   stop the installed copy, run that branch's latest commit
#   ./run-branch.sh .          the same with this folder as it is now (uncommitted changes too)
#   ./run-branch.sh --back     stop the test build, start the installed copy again
#   ./run-branch.sh --status   say which one is running
#
# - A branch runs from a snapshot of its latest commit in .worktrees/<branch> (a detached git
#   worktree), so a running test build never has its files changed underneath it. Run it again
#   to pick up new commits.
# - It borrows the installed copy's Python, Whisper model and word list (through run-dev.sh),
#   and uses its own settings (a fresh copy of the installed copy's, every time it starts),
#   log and data folders: ~/.config/ft-assistant-branch/, ~/.local/share/ft-assistant-branch/.
# - Its setup screen shows "Version ... test build (<branch>): not a public release".
# - Safety nets: a menu entry "FT Assistant: back to the installed version" while it runs;
#   if the test build stops by itself (a crash), the installed copy starts again by itself;
#   logging in always starts the installed copy.
set -u
REPO="$(dirname "$(readlink -f "$0")")"
SELF="$REPO/run-branch.sh"
LIVE="${XDG_DATA_HOME:-$HOME/.local/share}/ft-assistant"
LIVE_CONFIG="${XDG_CONFIG_HOME:-$HOME/.config}/ft-assistant"
BRANCH_CONFIG="${XDG_CONFIG_HOME:-$HOME/.config}/ft-assistant-branch"
BRANCH_DATA="${XDG_DATA_HOME:-$HOME/.local/share}/ft-assistant-branch"
STOPPING="$BRANCH_CONFIG/stopping"        # tells the supervisor the stop was on purpose
MENU_ENTRY="${XDG_DATA_HOME:-$HOME/.local/share}/applications/ft-assistant-back-to-installed.desktop"
READY_WAIT=60

say() { printf '%s\n' "$*"; }
fail() { say "$*" >&2; exit 1; }

# Process ids of FT Assistant processes (the app, its speech worker, its setup window) that
# belong to one copy: "installed" (no FT_ASSISTANT_CONFIG_DIR) or "branch".
copy_pids() {
  local want="$1" pid env cfg
  for pid in $(pgrep -f -- '[-]m ft_assistant|ft_assistant/whisper_worker[.]py'); do
    [ "$pid" = "$$" ] && continue
    env="$(tr '\0' '\n' < "/proc/$pid/environ" 2>/dev/null)" || continue
    cfg="$(printf '%s\n' "$env" | sed -n 's/^FT_ASSISTANT_CONFIG_DIR=//p' | head -n 1)"
    case "$want" in
      installed) [ -z "$cfg" ] && printf '%s\n' "$env" | grep -q "^FT_ASSISTANT_DATA_DIR=$LIVE\$" && echo "$pid";;
      branch) [ "$cfg" = "$BRANCH_CONFIG" ] && echo "$pid";;
    esac
  done
}
supervisor_pids() { pgrep -f -- "[r]un-branch[.]sh --supervise" | grep -vx "$$"; }

stop_pids() {      # TERM, wait up to 5 s, then KILL whatever is left
  local pids="$*" i
  [ -n "$pids" ] || return 0
  kill $pids 2>/dev/null
  for i in 1 2 3 4 5 6 7 8 9 10; do
    sleep 0.5
    kill -0 $pids 2>/dev/null || return 0
  done
  kill -9 $pids 2>/dev/null
  sleep 0.5
}

ready_lines() { local n; n="$(grep -c ' ready: ' "$1/ft-assistant.log" 2>/dev/null)"; echo "${n:-0}"; }
wait_ready() {     # wait for a new "ready:" line in that log; print it
  local dir="$1" before="$2" i
  for i in $(seq 1 $((READY_WAIT * 2))); do
    if [ "$(ready_lines "$dir")" -gt "$before" ]; then
      grep ' ready: ' "$dir/ft-assistant.log" | tail -n 1 | sed 's/^.* ready: /ready: /'
      return 0
    fi
    sleep 0.5
  done
  return 1
}

start_installed() {
  [ -x "$LIVE/ft-assistant" ] || fail "The installed FT Assistant wasn't found in $LIVE."
  local before; before="$(ready_lines "$LIVE_CONFIG")"
  env -u PYTHONPATH -u FT_DEV_SOURCE setsid "$LIVE/ft-assistant" >/dev/null 2>&1 < /dev/null &
  if line="$(wait_ready "$LIVE_CONFIG" "$before")"; then
    say "The installed FT Assistant is running again ($line)."
  else
    say "The installed FT Assistant didn't report ready within $READY_WAIT s."
    say "See $LIVE_CONFIG/ft-assistant.log."
    return 1
  fi
}

write_menu_entry() {
  mkdir -p "$(dirname "$MENU_ENTRY")"
  cat > "$MENU_ENTRY" <<EOF
[Desktop Entry]
Type=Application
Name=FT Assistant: back to the installed version
Comment=Stop the FT Assistant test build and start the installed version again
Exec="$SELF" --back
Icon=audio-input-microphone
Terminal=false
Categories=Utility;
EOF
}

# ---- the supervisor: runs the test build, and starts the installed copy if it stops by itself
if [ "${1:-}" = "--supervise" ]; then
  SRC="$2"
  env -u PYTHONPATH -u FT_ASSISTANT_CONFIG_DIR -u FT_ASSISTANT_DATA_DIR \
      -u FT_ASSISTANT_MODELS_DIR -u FT_ASSISTANT_MODEL -u FT_ASSISTANT_VOCAB \
      FT_DEV_SOURCE="$SRC" FT_DEV_CONFIG_DIR="$BRANCH_CONFIG" FT_DEV_DATA_DIR="$BRANCH_DATA" \
      "$REPO/run-dev.sh"
  if [ -e "$STOPPING" ]; then
    rm -f "$STOPPING"
    exit 0
  fi
  rm -f "$MENU_ENTRY"
  notify-send -a "FT Assistant" "FT Assistant test build stopped" \
    "It stopped by itself, so the installed version is starting again." 2>/dev/null
  start_installed
  exit 0
fi

case "${1:-}" in
  ""|-h|--help)
    sed -n '2,19p' "$SELF" | sed 's/^# \{0,1\}//'
    exit 0;;
  --status)
    if [ -n "$(copy_pids branch)" ]; then
      say "A test build is running: $(grep ' ready: ' "$BRANCH_CONFIG/ft-assistant.log" 2>/dev/null | tail -n 1 | sed 's/^.* ready: /ready: /')"
    elif [ -n "$(copy_pids installed)" ]; then
      say "The installed FT Assistant is running."
    else
      say "No FT Assistant is running."
    fi
    exit 0;;
  --back)
    mkdir -p "$BRANCH_CONFIG"
    PIDS="$(copy_pids branch)"
    if [ -n "$PIDS" ]; then
      touch "$STOPPING"
      stop_pids $PIDS
      for i in 1 2 3 4 5 6; do [ -z "$(supervisor_pids)" ] && break; sleep 0.5; done
      rm -f "$STOPPING"
      say "Stopped the test build."
    fi
    rm -f "$MENU_ENTRY"
    if [ -n "$(copy_pids installed)" ]; then
      say "The installed FT Assistant is already running."
    else
      start_installed
    fi
    exit $?;;
  -*)
    fail "Unknown option $1 (see ./run-branch.sh --help).";;
esac

# ---- run a branch (or this folder) in place of the installed copy
TARGET="$1"
git -C "$REPO" rev-parse --git-dir >/dev/null 2>&1 || fail "$REPO isn't a git checkout."
NOTE=""
if [ "$TARGET" = "." ]; then
  SRC="$REPO"
  BUILD="$(git -C "$REPO" branch --show-current)"
  BUILD="${BUILD:-detached}"
  [ -n "$(git -C "$REPO" status --porcelain --untracked-files=no)" ] && NOTE="with uncommitted changes"
else
  git -C "$REPO" rev-parse --verify --quiet "refs/heads/$TARGET" >/dev/null \
    || fail "There's no branch called \"$TARGET\". Branches: $(git -C "$REPO" branch --format='%(refname:short)' | tr '\n' ' ')"
  BUILD="$TARGET"
  SRC="$REPO/.worktrees/${TARGET//\//-}"
  if [ -e "$SRC/.git" ]; then
    [ -z "$(git -C "$SRC" status --porcelain --untracked-files=no)" ] \
      || fail "$SRC has changes of its own; it's only meant as a snapshot. Remove them first."
    git -C "$SRC" checkout --quiet --detach "refs/heads/$TARGET" || fail "Couldn't update $SRC."
  else
    git -C "$REPO" worktree add --quiet --detach "$SRC" "refs/heads/$TARGET" \
      || fail "Couldn't make the snapshot folder $SRC."
  fi
fi
[ -f "$SRC/ft_assistant/__main__.py" ] || fail "$TARGET doesn't contain FT Assistant (no ft_assistant/)."
COMMIT="$(git -C "$SRC" rev-parse --short HEAD)"

say "Switching to the test build: $BUILD ($COMMIT${NOTE:+, $NOTE})."
say "Dictation stops for a few seconds."

# Settings: a fresh copy of the installed copy's, so tests never change the real ones.
mkdir -p "$BRANCH_CONFIG" "$BRANCH_DATA"
[ -f "$LIVE_CONFIG/settings.json" ] && cp "$LIVE_CONFIG/settings.json" "$BRANCH_CONFIG/settings.json"

# Stop whatever runs now: an earlier test build (switching branches), then the installed copy.
PIDS="$(copy_pids branch)"
if [ -n "$PIDS" ]; then
  touch "$STOPPING"
  stop_pids $PIDS
  for i in 1 2 3 4 5 6; do [ -z "$(supervisor_pids)" ] && break; sleep 0.5; done
  rm -f "$STOPPING"
fi
stop_pids $(copy_pids installed)

BEFORE="$(ready_lines "$BRANCH_CONFIG")"
FT_ASSISTANT_BUILD="$BUILD" FT_ASSISTANT_BUILD_NOTE="$NOTE" \
  setsid "$SELF" --supervise "$SRC" >/dev/null 2>&1 < /dev/null &
write_menu_entry
if LINE="$(wait_ready "$BRANCH_CONFIG" "$BEFORE")"; then
  say "The test build is running ($LINE)."
  say "To go back: ./run-branch.sh --back, or \"FT Assistant: back to the installed version\" in the menu."
else
  say "The test build didn't report ready within $READY_WAIT s; see $BRANCH_CONFIG/ft-assistant.log."
  say "If it stopped, the installed version starts again by itself."
  exit 1
fi
