:<<"::CMDLITERAL"
@echo off
rem ---------------------------------------------------------------- Windows part
rem FT Assistant setup. Double-click this file. The Linux part below is skipped on Windows.
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -Command "$f='%~f0'; $t=[IO.File]::ReadAllText($f); $m='#__FT_ASSISTANT_'+'PS__'; $p=$t.Substring($t.IndexOf($m)+$m.Length); $e='#__FT_ASSISTANT_'+'INSTALLER__'; $p=$p.Substring(0,$p.IndexOf($e)); $env:FT_SETUP_FILE=$f; Invoke-Expression $p"
set "RC=%ERRORLEVEL%"
echo.
if not defined FT_SETUP_YES pause
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
say "Step 1 of 6: Checking what this computer already has (a few seconds)..."
say ""

[ "$(uname -s)" = "Linux" ] && [ "$(uname -m)" = "x86_64" ] \
  || fail "FT Assistant needs 64-bit Linux (x86_64) or Windows."
if [ "${XDG_SESSION_TYPE:-}" = "wayland" ] || { [ -n "${WAYLAND_DISPLAY:-}" ] && [ -z "${DISPLAY:-}" ]; }; then
  fail "This desktop session uses Wayland, which FT Assistant doesn't support yet.
Log out, choose an X11 (\"Xorg\") session at the login screen, and run setup again."
fi
[ -n "${DISPLAY:-}" ] || fail "No graphical desktop (X11) was found. Run setup from your desktop."

# ---- reuse what's already on this computer before downloading anything
PM=""
for m in apt-get dnf pacman zypper; do command -v "$m" >/dev/null 2>&1 && { PM="$m"; break; }; done
pkg_name() {   # generic name -> this system's package name
  case "$PM:$1" in
    apt-get:notify) echo libnotify-bin;;  dnf:notify|pacman:notify) echo libnotify;;  zypper:notify) echo libnotify-tools;;
    apt-get:portaudio) echo libportaudio2;;  *:portaudio) echo portaudio;;
    *) echo "$1";;
  esac
}
check_packages() {
  NEEDED=()
  for c in curl tar xdotool; do command -v "$c" >/dev/null 2>&1 || NEEDED+=("$(pkg_name "$c")"); done
  command -v notify-send >/dev/null 2>&1 || NEEDED+=("$(pkg_name notify)")
  ldconfig -p 2>/dev/null | grep -q 'libportaudio\.so\.2' || NEEDED+=("$(pkg_name portaudio)")
}
install_cmd() {
  case "$PM" in
    apt-get) echo "sudo apt-get install -y $*";;  dnf) echo "sudo dnf install -y $*";;
    pacman) echo "sudo pacman -S --needed --noconfirm $*";;  zypper) echo "sudo zypper install -y $*";;
  esac
}
check_packages
if [ ${#NEEDED[@]} -gt 0 ]; then
  say "Some system packages are missing: ${NEEDED[*]}"
  if [ -n "$PM" ]; then
    CMD="$(install_cmd "${NEEDED[@]}")"
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
  say ""
fi

GPU=no
if command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi -L 2>/dev/null | grep -q '^GPU'; then GPU=yes; fi
# The speech engine needs a driver for CUDA 12 or newer; an older one can't use the card at all.
CUDA_MAJOR="$(nvidia-smi 2>/dev/null | sed -n 's/.*CUDA Version: *\([0-9][0-9]*\).*/\1/p' | head -1)"
if [ "$GPU" = "yes" ] && [ -n "$CUDA_MAJOR" ] && [ "$CUDA_MAJOR" -lt 12 ]; then
  GPU=no
  say "Your NVIDIA driver is too old for the speech engine (it supports CUDA $CUDA_MAJOR; 12 or newer"
  say "is needed), so FT Assistant will use the processor. To use the graphics card instead,"
  say "update the NVIDIA driver and run setup again."
  say ""
fi
case "${FT_SETUP_GPU:-}" in yes|no) GPU="$FT_SETUP_GPU";; esac   # testing hook
MODEL="small.en"; [ "$GPU" = "yes" ] && MODEL="large-v3-turbo"
# FT Assistant's own Python (pinned; the values are in the installer embedded in this file).
pin() { sed -n "/^#__FT_ASSISTANT_INSTALLER__\$/,\$ s/^$1 = \"\([^\"]*\)\".*/\1/p" "$SELF" | head -n 1; }
RUNTIME_RELEASE="$(pin RUNTIME_RELEASE)"; RUNTIME_PYTHON="$(pin RUNTIME_PYTHON)"
RUNTIME_SHA256="$(pin RUNTIME_SHA256_LINUX)"; RUNTIME_MARKER="$(pin RUNTIME_MARKER)"
RUNTIME_ID="cpython-$RUNTIME_PYTHON+$RUNTIME_RELEASE"
[ -n "$RUNTIME_RELEASE" ] && [ -n "$RUNTIME_PYTHON" ] || fail "This setup file is damaged. Download it again."
runtime_ok() {    # $1/python is FT Assistant's own runtime of the pinned version, and it runs
  [ "$(cat "$1/python/$RUNTIME_MARKER" 2>/dev/null)" = "$RUNTIME_ID" ] && [ ! -e "$1/python/pyvenv.cfg" ] \
    && [ "$("$1/python/bin/python3" -I -c 'import sys; print(sys.version.split()[0])' 2>/dev/null)" = "$RUNTIME_PYTHON" ]
}
GPU_LIBS=pip
if [ "$GPU" = "yes" ] && ldconfig -p 2>/dev/null | grep -q 'libcublas\.so\.12' \
     && ldconfig -p 2>/dev/null | grep -q 'libcudnn\.so\.9'; then GPU_LIBS=system; fi
DEFAULT_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/ft-assistant"
existing_install() {   # an existing install's folder, from the menu or login entry it made
  local f d
  for f in "${XDG_DATA_HOME:-$HOME/.local/share}/applications/ft-assistant.desktop" \
           "${XDG_CONFIG_HOME:-$HOME/.config}/autostart/ft-assistant.desktop"; do
    [ -f "$f" ] || continue
    d=$(sed -n 's|^Exec="\{0,1\}\(.*\)/ft-assistant"\{0,1\}$|\1|p' "$f" | head -n 1)
    [ -n "$d" ] && [ -f "$d/install.json" ] && { echo "$d"; return 0; }
  done
  [ -f "$DEFAULT_DIR/install.json" ] && echo "$DEFAULT_DIR"
  return 0
}
EXISTING_DIR="$(existing_install)"
[ -n "$EXISTING_DIR" ] && DEFAULT_DIR="$EXISTING_DIR"   # updating: offer the same folder
DIR="${FT_SETUP_DIR:-}"
model_on_computer() {    # same places install.py looks (Hugging Face cache, install dir)
  local d
  for d in "${FT_ASSISTANT_MODEL_SOURCE:-}" "${HF_HUB_CACHE:-}" "${HF_HOME:+$HF_HOME/hub}" \
           "$HOME/.cache/huggingface/hub" "${1:-}/models"; do
    [ -n "$d" ] && compgen -G "$d/models--*--faster-whisper-$MODEL/snapshots/*/model.bin" >/dev/null && return 0
  done
  [ -s "${1:-}/models/$MODEL/model.bin" ] && return 0
  return 1
}

DL_MB=150; DISK_MB=350
say "What setup needs:"
if runtime_ok "${DIR:-$DEFAULT_DIR}"; then
  say "  Python runtime (FT Assistant's own)     already in the install folder (reused)"
else
  say "  Python runtime (FT Assistant's own)     about 70 MB download"; DL_MB=$((DL_MB+70)); DISK_MB=$((DISK_MB+200))
  say "  Smooth text for the setup window        about 2 MB download"; DL_MB=$((DL_MB+2))
fi
say "  Speech engine and audio libraries       about 150 MB download  (350 MB on disk)"
if [ "$GPU" = "yes" ]; then
  if [ "$GPU_LIBS" = "system" ]; then
    say "  NVIDIA GPU libraries                    already on this computer (reused)"
  else
    say "  NVIDIA GPU libraries                    about 1.3 GB download  (2.1 GB on disk)"; DL_MB=$((DL_MB+1300)); DISK_MB=$((DISK_MB+2100))
  fi
fi
if model_on_computer "${DIR:-$DEFAULT_DIR}"; then
  say "$(printf '  %-40s' "Whisper speech model ($MODEL)")already on this computer (reused, no extra disk space)"
else
  MB=500; SIZE="500 MB"; [ "$GPU" = "yes" ] && { MB=1600; SIZE="1.6 GB"; }
  say "$(printf '  %-40s' "Whisper speech model ($MODEL)")about $SIZE download  ($SIZE on disk)"; DL_MB=$((DL_MB+MB)); DISK_MB=$((DISK_MB+MB))
fi
TOTAL="  Total                                   about $DL_MB MB download, about $DISK_MB MB on disk"
say "  $(printf '%*s' $(( ${#TOTAL} - 2 )) '' | tr ' ' '-')"
say "$TOTAL"
say "  (Packages already in your pip download cache aren't downloaded again.)"
[ "$GPU" = "yes" ] || say "  No NVIDIA graphics card found, so the smaller model runs on the processor."
say "  If you then install Claude Code or OpenCode from the setup window: about 350-400 MB more."
say ""
NEED_KB=$(( (DISK_MB + 300) * 1000 ))

if [ -z "$DIR" ]; then
  if [ -n "$EXISTING_DIR" ]; then
    read -r -p "FT Assistant is installed in $DEFAULT_DIR. Press Enter to update it there, or type another folder: " DIR
  else
    read -r -p "Install to $DEFAULT_DIR? Press Enter, or type another folder: " DIR
  fi
fi
DIR="${DIR:-$DEFAULT_DIR}"
DIR="${DIR/#\~/$HOME}"
mkdir -p "$DIR" 2>/dev/null || fail "Can't create the folder $DIR."
DIR="$(cd "$DIR" && pwd)"
FREE_KB=$(df -Pk "$DIR" | awk 'NR==2 {print $4}')
[ "${FREE_KB:-0}" -ge "$NEED_KB" ] || fail "Not enough free space in $DIR (needs about $((NEED_KB/1000)) MB)."
if [ -f "$DIR/install.json" ]; then say "FT Assistant is already installed there; it will be repaired/reinstalled."; fi

if [ -z "${FT_SETUP_YES:-}" ]; then
  read -r -p "Press Enter to start, or Ctrl+C to cancel. " _
fi
say ""

download_python() {
  rm -rf "$DIR/python"
  if [ -n "${FT_SETUP_PYTHON_TARBALL:-}" ]; then              # testing hook
    tar -xzf "$FT_SETUP_PYTHON_TARBALL" -C "$DIR" || fail "Couldn't unpack the Python runtime."
  else
    say "  Downloading Python $RUNTIME_PYTHON for FT Assistant (about 70 MB):"
    ARCHIVE="$DIR/python-download.tar.gz"
    curl -fL --progress-bar -o "$ARCHIVE" \
      "https://github.com/astral-sh/python-build-standalone/releases/download/$RUNTIME_RELEASE/cpython-$RUNTIME_PYTHON%2B$RUNTIME_RELEASE-x86_64-unknown-linux-gnu-install_only.tar.gz" \
      || { rm -f "$ARCHIVE"; fail "The Python download failed. Check your internet connection and try again."; }
    [ "$(sha256sum "$ARCHIVE" | cut -d' ' -f1)" = "$RUNTIME_SHA256" ] \
      || { rm -f "$ARCHIVE"; fail "The Python download is damaged (wrong checksum). Try again."; }
    tar -xzf "$ARCHIVE" -C "$DIR" || { rm -f "$ARCHIVE"; fail "Couldn't unpack the Python runtime."; }
    rm -f "$ARCHIVE"
  fi
  printf '%s\n' "$RUNTIME_ID" > "$DIR/python/$RUNTIME_MARKER"
}
run_installer() {
  PYTHONNOUSERSITE=1 "$DIR/python/bin/python3" "$DIR/install.py" install --dir "$DIR" --gpu "$GPU" \
    --gpu-libs "$GPU_LIBS" --python-source standalone "$@"
}

sed -n '/^#__FT_ASSISTANT_INSTALLER__$/,$p' "$SELF" | tail -n +2 > "$DIR/install.py"
say "Step 2 of 6: Python"
if runtime_ok "$DIR"; then
  say "  FT Assistant's own Python $RUNTIME_PYTHON is already there (reused, nothing downloaded)."
else
  download_python
fi
run_installer "$@"
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
Say 'Step 1 of 6: Checking what this computer already has (a few seconds)...'
Say ''
if (-not [Environment]::Is64BitOperatingSystem) { Fail 'FT Assistant needs 64-bit Windows.' }
$gpu = 'no'
try {
  if (Get-CimInstance Win32_VideoController | Where-Object { $_.Name -match 'NVIDIA' }) { $gpu = 'yes' }
} catch { }
# The speech engine needs a driver for CUDA 12 or newer; an older one can't use the card at all.
function Get-CudaMajor {
  $smi = @($env:FT_SETUP_NVIDIA_SMI,     # testing hook: a pretend nvidia-smi
           (Get-Command nvidia-smi.exe -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty Source),
           (Join-Path $env:ProgramFiles 'NVIDIA Corporation\NVSMI\nvidia-smi.exe')) |
         Where-Object { $_ -and (Test-Path -LiteralPath $_) } | Select-Object -First 1
  if (-not $smi) { return $null }
  try { $out = (& $smi 2>$null) -join "`n" } catch { return $null }
  if ($out -match 'CUDA Version:\s*(\d+)') { return [int]$Matches[1] }
  return $null
}
if ($gpu -eq 'yes') {
  $cudaMajor = Get-CudaMajor
  if ($cudaMajor -and $cudaMajor -lt 12) {
    $gpu = 'no'
    Say "Your NVIDIA driver is too old for the speech engine (it supports CUDA ${cudaMajor}; 12 or newer"
    Say 'is needed), so FT Assistant will use the processor. To use the graphics card instead,'
    Say 'update the NVIDIA driver and run setup again.'
    Say ''
  }
}
if ($env:FT_SETUP_GPU -in @('yes', 'no')) { $gpu = $env:FT_SETUP_GPU }   # testing hook (Wine has no CUDA)
$model = if ($gpu -eq 'yes') { 'large-v3-turbo' } else { 'small.en' }
$default = Join-Path $env:LOCALAPPDATA 'FT Assistant'
# Updating: offer the folder FT Assistant is already installed in (recorded in its uninstall
# entry since 0.1.0), so pressing Enter updates it rather than making a second install.
function Find-ExistingInstall {
  try {
    $loc = (Get-ItemProperty -Path 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\FTAssistant' -ErrorAction Stop).InstallLocation
    if ($loc -and (Test-Path -LiteralPath (Join-Path $loc 'install.json'))) { return $loc }
  } catch { }
  if (Test-Path -LiteralPath (Join-Path $default 'install.json')) { return $default }
  return $null
}
$existing = Find-ExistingInstall
if ($existing) { $default = $existing }

# ---- FT Assistant's own Python (pinned; the values are in the installer embedded in this file)
$text = [IO.File]::ReadAllText($env:FT_SETUP_FILE)
function Get-Pin($name) {
  if ($text -match ('(?m)^' + $name + ' = "([^"]*)"')) { return $Matches[1] }
  return $null
}
$rtRelease = Get-Pin 'RUNTIME_RELEASE'; $rtPython = Get-Pin 'RUNTIME_PYTHON'
$rtSha = Get-Pin 'RUNTIME_SHA256_WINDOWS'; $rtMarker = Get-Pin 'RUNTIME_MARKER'
if (-not $rtRelease -or -not $rtPython -or -not $rtMarker) { Fail 'This setup file is damaged. Download it again.' }
$rtId = "cpython-$rtPython+$rtRelease"
# True if <folder>\python is FT Assistant's own runtime of the pinned version, and it runs.
function Test-OwnPython($folder) {
  $py = Join-Path $folder 'python\python.exe'
  $marker = Join-Path $folder "python\$rtMarker"
  if (-not (Test-Path -LiteralPath $marker) -or -not (Test-Path -LiteralPath $py)) { return $false }
  if ((Get-Content -LiteralPath $marker -Raw).Trim() -ne $rtId) { return $false }
  if (Test-Path -LiteralPath (Join-Path $folder 'python\pyvenv.cfg')) { return $false }
  try { $v = (& $py -I -c 'import sys; print(sys.version.split()[0])' 2>$null) } catch { return $false }
  return ("$v".Trim() -eq $rtPython)
}
$gpuLibs = 'pip'
function Test-OnPath($file) {
  foreach ($d in ($env:PATH -split ';')) { if ($d -and (Test-Path -LiteralPath (Join-Path $d $file))) { return $true } }
  return $false
}
if ($gpu -eq 'yes' -and (Test-OnPath 'cublas64_12.dll') -and (Test-OnPath 'cudnn64_9.dll')) { $gpuLibs = 'system' }
function Test-ModelOnComputer($installDir) {
  $dirs = @($env:FT_ASSISTANT_MODEL_SOURCE, $env:HF_HUB_CACHE)
  if ($env:HF_HOME) { $dirs += (Join-Path $env:HF_HOME 'hub') }
  $own = Join-Path $installDir "models\$model\model.bin"
  if ((Test-Path $own) -and (Get-Item $own).Length -gt 0) { return $true }
  $dirs += (Join-Path $env:USERPROFILE '.cache\huggingface\hub')
  foreach ($d in $dirs) {
    if ($d -and (Test-Path $d)) {
      if (Get-ChildItem -Path $d -Directory -Filter "models--*--faster-whisper-$model" -ErrorAction SilentlyContinue |
          Where-Object { Get-ChildItem -Path (Join-Path $_.FullName 'snapshots') -Recurse -Filter model.bin -ErrorAction SilentlyContinue }) { return $true }
    }
  }
  return $false
}

$dl = 150; $disk = 350
$probeDir = if ($env:FT_SETUP_DIR) { $env:FT_SETUP_DIR } else { $default }
Say 'What setup needs:'
if (Test-OwnPython $probeDir) { Say "  Python runtime (FT Assistant's own)     already in the install folder (reused)" }
else { Say "  Python runtime (FT Assistant's own)     about 50 MB download"; $dl += 50; $disk += 150 }
Say '  Speech engine and audio libraries       about 150 MB download  (350 MB on disk)'
if ($gpu -eq 'yes') {
  if ($gpuLibs -eq 'system') { Say '  NVIDIA GPU libraries                    already on this computer (reused)' }
  else { Say '  NVIDIA GPU libraries                    about 1.3 GB download  (2.1 GB on disk)'; $dl += 1300; $disk += 2100 }
}
$modelLabel = '  {0,-40}' -f "Whisper speech model ($model)"
if (Test-ModelOnComputer $probeDir) { Say "${modelLabel}already on this computer (reused)" }
else {
  if ($gpu -eq 'yes') { $mb = 1600; $size = '1.6 GB' } else { $mb = 500; $size = '500 MB' }
  Say "${modelLabel}about $size download  ($size on disk)"; $dl += $mb; $disk += $mb
}
$total = "  Total                                   about $dl MB download, about $disk MB on disk"
Say ('  ' + ('-' * ($total.Length - 2)))
Say $total
Say "  (Packages already in your pip download cache aren't downloaded again.)"
if ($gpu -ne 'yes') { Say '  No NVIDIA graphics card found, so the smaller model runs on the processor.' }
Say '  If you then install Claude Code or OpenCode from the setup window: about 350-400 MB more.'
Say ''

$dir = $env:FT_SETUP_DIR
if (-not $dir) {
  if ($existing) { $dir = Read-Host "FT Assistant is installed in ${default}. Press Enter to update it there, or type another folder" }
  else { $dir = Read-Host "Install to ${default}? Press Enter, or type another folder" }
}
if (-not $dir) { $dir = $default }
New-Item -ItemType Directory -Force -Path $dir | Out-Null
$dir = (Resolve-Path $dir).Path
if (Test-Path (Join-Path $dir 'install.json')) { Say 'FT Assistant is already installed there; it will be repaired/reinstalled.' }
if (-not $env:FT_SETUP_YES) { Read-Host 'Press Enter to start, or close this window to cancel' | Out-Null }
Say ''

function Get-OwnPython {
  $pyDir = Join-Path $dir 'python'
  if (Test-Path $pyDir) { Remove-Item -Recurse -Force $pyDir }
  $given = $env:FT_SETUP_PYTHON_TARBALL                     # testing hook
  if ($given) { $tgz = $given } else {
    Say "  Downloading Python $rtPython for FT Assistant (about 50 MB)..."
    $tgz = Join-Path $dir 'python-download.tar.gz'
    $url = "https://github.com/astral-sh/python-build-standalone/releases/download/$rtRelease/cpython-$rtPython%2B$rtRelease-x86_64-pc-windows-msvc-install_only.tar.gz"
    $ProgressPreference = 'SilentlyContinue'                # much faster in Windows PowerShell
    try { Invoke-WebRequest -UseBasicParsing -Uri $url -OutFile $tgz }
    catch { Remove-Item -Force $tgz -ErrorAction SilentlyContinue; Fail 'The Python download failed. Check your internet connection and try again.' }
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $tgz).Hash.ToLower() -ne $rtSha) {
      Remove-Item -Force $tgz -ErrorAction SilentlyContinue
      Fail 'The Python download is damaged (wrong checksum). Try again.'
    }
  }
  tar -xzf $tgz -C $dir
  $unpacked = $LASTEXITCODE
  if (-not $given) { Remove-Item -Force $tgz -ErrorAction SilentlyContinue }
  if ($unpacked -ne 0) { Fail "Couldn't unpack the Python runtime." }
  Set-Content -LiteralPath (Join-Path $pyDir $rtMarker) -Value $rtId -Encoding ASCII
}

$mark = '#__FT_ASSISTANT_' + 'INSTALLER__'
$code = $text.Substring($text.IndexOf("`n" + $mark) + $mark.Length + 2)
[IO.File]::WriteAllText((Join-Path $dir 'install.py'), $code)
# A running FT Assistant keeps files in its folder open, and Windows can't delete open files,
# so stop it (and its speech engine and setup window) before replacing anything: otherwise
# repairing an existing install fails on the old Python folder. Matched two ways, because the
# lock file can't be read while the app holds it, and with a reused Python the app's process
# runs from that Python's folder rather than the install folder:
#   - any program started from the install folder
#   - any Python running FT Assistant's modules ("-m ft_assistant...")
function Stop-RunningApp {
  $ids = @()
  $prefix = $dir.TrimEnd('\') + '\'
  foreach ($p in @(Get-Process -ErrorAction SilentlyContinue)) {
    try { if ($p.Path -and $p.Path.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) { $ids += $p.Id } } catch { }
  }
  try {
    foreach ($p in @(Get-CimInstance Win32_Process -ErrorAction Stop)) {
      if ($p.CommandLine -and $p.CommandLine -match '-m\s+ft_assistant(\.|\s|$)') { $ids += [int]$p.ProcessId }
    }
  } catch { }
  $ids = @($ids | Where-Object { $_ -ne $PID } | Sort-Object -Unique)
  if ($ids.Count -eq 0) { return }
  # (taskkill complains about a process already ended with its parent: harmless, so ignored)
  foreach ($i in $ids) { try { & taskkill /PID $i /T /F 2>$null | Out-Null } catch { } }
  Start-Sleep -Seconds 2
  Say 'Stopped the running FT Assistant.'
}
Stop-RunningApp

Say 'Step 2 of 6: Python'
$env:PYTHONNOUSERSITE = '1'
$extra = @()
if ($env:FT_SETUP_INSTALL_ARGS) { $extra = $env:FT_SETUP_INSTALL_ARGS -split ' ' }   # testing hook
if (Test-OwnPython $dir) { Say "  FT Assistant's own Python $rtPython is already there (reused, nothing downloaded)." }
else { Get-OwnPython }
& (Join-Path $dir 'python\python.exe') (Join-Path $dir 'install.py') install --dir $dir --gpu $gpu --gpu-libs $gpuLibs --python-source standalone @extra
$rc = $LASTEXITCODE
if ($rc -ne 0) { Say "Setup didn't finish (error $rc). You can run it again." }
exit $rc
#__FT_ASSISTANT_INSTALLER__
