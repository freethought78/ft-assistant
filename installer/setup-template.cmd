:<<"::CMDLITERAL"
@echo off
rem ---------------------------------------------------------------- Windows part
rem FT Assistant setup. Double-click this file. The Linux part below is skipped on Windows.
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -Command "$f='%~f0'; $t=[IO.File]::ReadAllText($f); $m='#__FT_ASSISTANT_'+'PS__'; $p=$t.Substring($t.IndexOf($m)+$m.Length); $e='#__FT_ASSISTANT_'+'INSTALLER__'; $p=$p.Substring(0,$p.IndexOf($e)); $env:FT_SETUP_FILE=$f; Invoke-Expression $p"
set "RC=%ERRORLEVEL%"
echo.
pause
exit /b %RC%
::CMDLITERAL
# ---------------------------------------------------------------- Linux part
# FT Assistant setup. Run with:  bash FT-Assistant-setup.cmd
# (The Windows part above is skipped on Linux.)
set -u
SELF="$(readlink -f "$0")"
say() { printf '%s\n' "$*"; }
fail() { say ""; say "$*"; say ""; exit 1; }

say ""
say "FT Assistant setup"
say "=================="
say "Please wait a moment while requirements are checked..."
say ""

[ "$(uname -s)" = "Linux" ] && [ "$(uname -m)" = "x86_64" ] \
  || fail "FT Assistant needs 64-bit Linux (x86_64) or Windows."
if [ "${XDG_SESSION_TYPE:-}" = "wayland" ] || { [ -n "${WAYLAND_DISPLAY:-}" ] && [ -z "${DISPLAY:-}" ]; }; then
  fail "This desktop session uses Wayland, which FT Assistant doesn't support yet.
Log out, choose an X11 (\"Xorg\") session at the login screen, and run setup again."
fi
[ -n "${DISPLAY:-}" ] || fail "No graphical desktop (X11) was found. Run setup from your desktop."

# ---- system packages: some are needed, python3-tk makes the setup window's text smooth
PM=""
for m in apt-get dnf pacman zypper; do command -v "$m" >/dev/null 2>&1 && { PM="$m"; break; }; done
pkg_name() {   # generic name -> this system's package name
  case "$PM:$1" in
    apt-get:notify) echo libnotify-bin;;  dnf:notify|pacman:notify) echo libnotify;;  zypper:notify) echo libnotify-tools;;
    apt-get:portaudio) echo libportaudio2;;  *:portaudio) echo portaudio;;
    dnf:tk) echo python3-tkinter;;  pacman:tk) echo tk;;  *:tk) echo python3-tk;;
    *) echo "$1";;
  esac
}
smooth_tk() {  # the system's Python can open windows with smooth (Xft) fonts
  command -v python3 >/dev/null 2>&1 && python3 - <<'PYEOF' >/dev/null 2>&1
import sys, tkinter
assert sys.version_info >= (3, 8)
r = tkinter.Tk(); r.withdraw()
assert str(r.tk.call("::tk::pkgconfig", "get", "fontsystem")) == "xft"
PYEOF
}
check_packages() {
  NEEDED=(); OPTIONAL=()
  for c in curl tar xdotool; do command -v "$c" >/dev/null 2>&1 || NEEDED+=("$(pkg_name "$c")"); done
  command -v notify-send >/dev/null 2>&1 || NEEDED+=("$(pkg_name notify)")
  ldconfig -p 2>/dev/null | grep -q 'libportaudio\.so\.2' || NEEDED+=("$(pkg_name portaudio)")
  smooth_tk || OPTIONAL+=("$(pkg_name tk)")
}
install_cmd() {
  case "$PM" in
    apt-get) echo "sudo apt-get install -y $*";;  dnf) echo "sudo dnf install -y $*";;
    pacman) echo "sudo pacman -S --needed --noconfirm $*";;  zypper) echo "sudo zypper install -y $*";;
  esac
}
check_packages
if [ ${#NEEDED[@]} -gt 0 ] || [ ${#OPTIONAL[@]} -gt 0 ]; then
  ALL=("${NEEDED[@]}" "${OPTIONAL[@]}")
  say "Some system packages are missing:"
  [ ${#NEEDED[@]} -gt 0 ] && say "  needed:      ${NEEDED[*]}"
  [ ${#OPTIONAL[@]} -gt 0 ] && say "  recommended: ${OPTIONAL[*]}  (clear, smooth text in the setup window)"
  if [ -n "$PM" ]; then
    CMD="$(install_cmd "${ALL[@]}")"
    say "They can be installed now with:  $CMD"
    ANSWER="n"
    if [ -z "${FT_SETUP_YES:-}" ]; then
      read -r -p "Install them now? You'll be asked for your password. [Y/n] " ANSWER
      ANSWER="${ANSWER:-y}"
    fi
    case "$ANSWER" in
      [Yy]*) $CMD || say "The install didn't finish.";;
    esac
    check_packages
  fi
  if [ ${#NEEDED[@]} -gt 0 ]; then
    fail "These are still missing: ${NEEDED[*]}
Install them (${CMD:-with the package manager}), then run setup again."
  fi
  [ ${#OPTIONAL[@]} -gt 0 ] && say "Continuing without ${OPTIONAL[*]}; the setup window will use a plainer font."
  say ""
fi

GPU=no
if command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi -L 2>/dev/null | grep -q '^GPU'; then GPU=yes; fi
DEFAULT_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/ft-assistant"
DIR="${FT_SETUP_DIR:-}"

say "What will be downloaded:"
say "  Python runtime                          about 70 MB"
say "  Speech engine and audio libraries       about 150 MB   (350 MB on disk)"
if [ "$GPU" = "yes" ]; then
  say "  NVIDIA GPU libraries                    about 1.3 GB   (2.1 GB on disk)"
  say "  Whisper speech model (large-v3-turbo)   about 1.6 GB"
  say "  ------------------------------------------------------------"
  say "  Total                                   about 3.1 GB   (about 4.2 GB on disk)"
  NEED_KB=4500000
else
  say "  Whisper speech model (small.en)         about 0.5 GB"
  say "  ------------------------------------------------------------"
  say "  Total                                   about 0.7 GB   (about 1 GB on disk)"
  say "  (No NVIDIA graphics card found, so the smaller model runs on the processor.)"
  NEED_KB=1100000
fi
say "  If you then install Claude Code or OpenCode from the setup window: about 350-400 MB more."
say ""

if [ -z "$DIR" ]; then
  read -r -p "Install to $DEFAULT_DIR? Press Enter, or type another folder: " DIR
fi
DIR="${DIR:-$DEFAULT_DIR}"
DIR="${DIR/#\~/$HOME}"
mkdir -p "$DIR" 2>/dev/null || fail "Can't create the folder $DIR."
DIR="$(cd "$DIR" && pwd)"
FREE_KB=$(df -Pk "$DIR" | awk 'NR==2 {print $4}')
[ "${FREE_KB:-0}" -ge "$NEED_KB" ] || fail "Not enough free space in $DIR (needs about $((NEED_KB/1000000)) GB more)."
if [ -f "$DIR/install.json" ]; then say "FT Assistant is already installed there; it will be repaired/reinstalled."; fi

if [ -z "${FT_SETUP_YES:-}" ]; then
  read -r -p "Press Enter to start the download and install, or Ctrl+C to cancel. " _
fi

say ""
say "Downloading the Python runtime..."
if [ -n "${FT_SETUP_PYTHON_TARBALL:-}" ]; then
  tar -xzf "$FT_SETUP_PYTHON_TARBALL" -C "$DIR" || fail "Couldn't unpack the Python runtime."
else
  URL=$(curl -fsSL https://api.github.com/repos/astral-sh/python-build-standalone/releases/latest \
    | grep -o '"browser_download_url": *"[^"]*cpython-3\.12\.[0-9]*\(+\|%2B\)[0-9]*-x86_64-unknown-linux-gnu-install_only\.tar\.gz"' \
    | head -n 1 | sed 's/.*"\(https[^"]*\)"$/\1/')
  [ -n "$URL" ] || fail "Couldn't find the Python download. Check your internet connection and try again."
  curl -fL --progress-bar "$URL" | tar -xz -C "$DIR" || fail "The Python download failed. Try again."
fi

sed -n '/^#__FT_ASSISTANT_INSTALLER__$/,$p' "$SELF" | tail -n +2 > "$DIR/install.py"
PYTHONNOUSERSITE=1 "$DIR/python/bin/python3" "$DIR/install.py" install --dir "$DIR" --gpu "$GPU" "$@"
RC=$?
[ $RC -eq 0 ] || say "Setup didn't finish (error $RC). You can run it again; it picks up where it left off."
exit $RC
#__FT_ASSISTANT_PS__
# ---------------------------------------------------------------- Windows part (PowerShell)
$ErrorActionPreference = 'Stop'
function Say($s) { Write-Host $s }
function Fail($s) { Write-Host ''; Write-Host $s; exit 1 }

Say ''
Say 'FT Assistant setup'
Say '=================='
Say 'Please wait a moment while requirements are checked...'
Say ''
if (-not [Environment]::Is64BitOperatingSystem) { Fail 'FT Assistant needs 64-bit Windows.' }
$gpu = 'no'
try {
  if (Get-CimInstance Win32_VideoController | Where-Object { $_.Name -match 'NVIDIA' }) { $gpu = 'yes' }
} catch { }
$default = Join-Path $env:LOCALAPPDATA 'FT Assistant'

Say 'What will be downloaded:'
Say '  Python runtime                          about 50 MB'
Say '  Speech engine and audio libraries       about 150 MB   (350 MB on disk)'
if ($gpu -eq 'yes') {
  Say '  NVIDIA GPU libraries                    about 1.3 GB   (2.1 GB on disk)'
  Say '  Whisper speech model (large-v3-turbo)   about 1.6 GB'
  Say '  ------------------------------------------------------------'
  Say '  Total                                   about 3.1 GB   (about 4.2 GB on disk)'
} else {
  Say '  Whisper speech model (small.en)         about 0.5 GB'
  Say '  ------------------------------------------------------------'
  Say '  Total                                   about 0.7 GB   (about 1 GB on disk)'
  Say '  (No NVIDIA graphics card found, so the smaller model runs on the processor.)'
}
Say '  If you then install Claude Code or OpenCode from the setup window: about 350-400 MB more.'
Say ''

$dir = $env:FT_SETUP_DIR
if (-not $dir) { $dir = Read-Host "Install to $default? Press Enter, or type another folder" }
if (-not $dir) { $dir = $default }
New-Item -ItemType Directory -Force -Path $dir | Out-Null
$dir = (Resolve-Path $dir).Path
if (Test-Path (Join-Path $dir 'install.json')) { Say 'FT Assistant is already installed there; it will be repaired/reinstalled.' }
if (-not $env:FT_SETUP_YES) { Read-Host 'Press Enter to start the download and install, or close this window to cancel' | Out-Null }

Say ''
Say 'Downloading the Python runtime...'
$tgz = Join-Path $env:TEMP 'ft-assistant-python.tar.gz'
if ($env:FT_SETUP_PYTHON_TARBALL) { $tgz = $env:FT_SETUP_PYTHON_TARBALL } else {
  $rel = Invoke-RestMethod -UseBasicParsing 'https://api.github.com/repos/astral-sh/python-build-standalone/releases/latest'
  $asset = $rel.assets | Where-Object { $_.name -match '^cpython-3\.12\.\d+\+\d+-x86_64-pc-windows-msvc-install_only\.tar\.gz$' } | Select-Object -First 1
  if (-not $asset) { Fail "Couldn't find the Python download. Check your internet connection and try again." }
  Invoke-WebRequest -UseBasicParsing -Uri $asset.browser_download_url -OutFile $tgz
}
tar -xzf $tgz -C $dir
if ($LASTEXITCODE -ne 0) { Fail "Couldn't unpack the Python runtime." }

$text = [IO.File]::ReadAllText($env:FT_SETUP_FILE)
$mark = '#__FT_ASSISTANT_' + 'INSTALLER__'
$code = $text.Substring($text.IndexOf("`n" + $mark) + $mark.Length + 2)
[IO.File]::WriteAllText((Join-Path $dir 'install.py'), $code)
$env:PYTHONNOUSERSITE = '1'
& (Join-Path $dir 'python\python.exe') (Join-Path $dir 'install.py') install --dir $dir --gpu $gpu
if ($LASTEXITCODE -ne 0) { Say "Setup didn't finish (error $LASTEXITCODE). You can run it again." }
exit $LASTEXITCODE
#__FT_ASSISTANT_INSTALLER__
