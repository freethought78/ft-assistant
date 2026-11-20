"""Starting Claude Code / OpenCode in a visible terminal window, and recognising their windows.

Nothing here ever runs an agent in the background: every session is a normal, visible,
interactive terminal window the user can watch and talk to."""

import base64
import os
import platform
import re
import shutil
import sqlite3
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from . import config


@dataclass(frozen=True)
class Harness:
    key: str
    name: str
    exe: str

    def argv(self, folder, prompt, resume=None):
        """Command that opens an interactive session in `folder`, sending `prompt` if given.

        resume: continue an earlier conversation instead of starting a new one
          Claude Code: True  -> `--continue` (most recent conversation in `folder`)
          OpenCode:    an id -> `--session <id>`"""
        if self.key == "claude":
            return [self.exe] + (["--continue"] if resume else []) + ([prompt] if prompt else [])
        if self.key == "opencode":
            return ([self.exe, str(folder)] + (["--session", resume] if resume else [])
                    + (["--prompt", prompt] if prompt else []))
        raise ValueError(self.key)


HARNESSES = {
    "claude": Harness("claude", "Claude Code", "claude"),
    "opencode": Harness("opencode", "OpenCode", "opencode"),
}

# Window titles the CLIs set on their terminal (fallback detection for windows we didn't open).
_OPENCODE_TITLE = re.compile(r"^OC \| ")
_CLAUDE_TITLE = re.compile(r"^[^\w\s] \S")      # "✳ Conversation name" (glyph varies)
_CLAUDE_PLAIN = re.compile(r"^Claude Code\b")


def harness_from_title(title):
    """Best guess at which harness a terminal window title belongs to, or None."""
    title = title or ""
    if _OPENCODE_TITLE.match(title):
        return "opencode"
    if _CLAUDE_TITLE.match(title) or _CLAUDE_PLAIN.match(title):
        return "claude"
    return None


def clean_env(base=None):
    """Environment for a new agent: drop anything inherited from a Claude/Anthropic session
    (an inherited "child session" marker turns off Claude Code's transcripts and titles)."""
    env = dict(os.environ if base is None else base)
    for k in list(env):
        if k.startswith(("CLAUDE", "ANTHROPIC")):
            del env[k]
    return env


def claude_project_dir(folder, home=None):
    """Where Claude Code keeps the conversations started in `folder`."""
    base = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path(home or Path.home()) / ".claude")
    return base / "projects" / re.sub(r"[^A-Za-z0-9-]", "-", str(folder))


def last_conversation(harness_key, folder):
    """What to pass as `resume` to continue the newest conversation started in `folder`,
    or None if there isn't one yet (then a new conversation starts)."""
    try:
        if harness_key == "claude":
            return True if any(claude_project_dir(folder).glob("*.jsonl")) else None
        if harness_key == "opencode":
            db = Path.home() / ".local" / "share" / "opencode" / "opencode.db"
            if not db.exists():
                return None
            con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
            try:
                row = con.execute(
                    "select id from session where directory = ? and parent_id is null "
                    "and time_archived is null order by time_updated desc limit 1",
                    (str(folder),)).fetchone()
            finally:
                con.close()
            return row[0] if row else None
    except (OSError, sqlite3.Error):
        return None
    return None


def _node_version(bin_dir):
    """Sort key for an nvm folder like ~/.nvm/versions/node/v24.19.0/bin (newest first)."""
    nums = re.findall(r"\d+", bin_dir.parent.name)
    return tuple(int(n) for n in nums)


def install_dirs(home=None, env=None, windows=sys.platform == "win32"):
    """Usual places Claude Code and OpenCode get installed to. An app started at login often
    can't see them: shells add them to the search path in their start-up files (nvm, for
    example, does it in ~/.bashrc), which the desktop never reads."""
    env = os.environ if env is None else env
    home = Path(home or Path.home())
    dirs = [home / ".local" / "bin", home / ".claude" / "local", home / ".opencode" / "bin"]
    if windows:
        dirs.append(Path(env.get("APPDATA") or home / "AppData" / "Roaming") / "npm")
    else:
        dirs += [home / ".npm-global" / "bin", home / ".volta" / "bin", home / ".bun" / "bin",
                 home / ".asdf" / "shims"]
        nvm = Path(env.get("NVM_DIR") or home / ".nvm") / "versions" / "node"
        dirs += sorted(nvm.glob("*/bin"), key=_node_version, reverse=True)
    return dirs


def find_exe(h, which=shutil.which, dirs=None):
    """Full path of the harness's program: from the search path, else from the usual install
    places. None if it isn't installed."""
    found = which(h.exe)
    if found:
        return found
    for d in install_dirs() if dirs is None else dirs:
        found = which(h.exe, path=str(d))
        if found:
            return found
    return None


def with_dir_on_path(env, folder):
    """`env` with `folder` at the front of PATH (so a program found outside the search path also
    finds its helpers, such as nvm's node next to it)."""
    env = dict(env)
    parts = [p for p in env.get("PATH", "").split(os.pathsep) if p]
    if str(folder) not in parts:
        env["PATH"] = os.pathsep.join([str(folder)] + parts)
    return env


def terminal_command(argv, folder, which=shutil.which, windows=sys.platform == "win32"):
    """Wrap `argv` so it runs in a new window of the system's default terminal.

    Windows: the program itself, started in a new console window (see new_window_kwargs).
    Windows 11 shows that in Windows Terminal when it's the default terminal, with the
    arguments untouched. (Starting it through wt.exe instead broke them: wt re-parses its
    command line, dropping the quotes around "FT Assistant sessions" and splitting on ";", so
    OpenCode got a folder that didn't exist and closed at once.)"""
    if windows:
        exe = which(argv[0]) or argv[0]       # full path (claude.exe / opencode.exe)
        return [exe] + list(argv[1:])
    if which("gnome-terminal"):
        return ["gnome-terminal", f"--working-directory={folder}", "--"] + argv
    for term in ("x-terminal-emulator", "xfce4-terminal", "konsole", "mate-terminal",
                 "tilix", "kitty", "alacritty", "xterm"):
        if which(term):
            # "-e" with separate args is accepted by these (konsole/xterm/x-terminal-emulator…)
            return [term, "-e"] + argv
    raise RuntimeError("no terminal program found")


def new_window_kwargs(cmd):
    """subprocess.Popen options so the command gets its own visible window and outlives us."""
    if sys.platform != "win32":
        return {"start_new_session": True}
    CREATE_NEW_CONSOLE = 0x10
    return {"creationflags": CREATE_NEW_CONSOLE}


def open_session(harness_key, prompt, launcher=subprocess.Popen):
    """Open a visible terminal window with the chosen harness in the neutral folder,
    continuing the last conversation there (one ongoing conversation, no build-up)."""
    h = HARNESSES[harness_key]
    exe = find_exe(h)
    if not exe:
        raise RuntimeError(f"{h.name} isn't installed. Say \"Assistant setup\" to install it.")
    folder = config.sessions_dir()
    folder.mkdir(parents=True, exist_ok=True)
    resume = last_conversation(harness_key, folder)
    argv = h.argv(folder, prompt, resume)
    argv[0] = exe              # the full path: the terminal may not find it on its own
    cmd = terminal_command(argv, folder)
    env = with_dir_on_path(clean_env(), Path(exe).parent)
    launcher(cmd, cwd=str(folder), env=env, **std_handles(), **new_window_kwargs(cmd))
    return h


def std_handles(windows=sys.platform == "win32"):
    """Input/output for the agent's window. Linux: none from us (the terminal program gives the
    agent its own). Windows: leave them alone, so the agent uses its new console window. Passing
    NUL there (as Linux does) made the agent read and write nowhere, and it quit at once."""
    if windows:
        return {}
    return {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL}


# ---------------------------------------------------------------- installing an assistant
# Always the latest version from the official source, run in a visible window after the user
# agrees. Linux: each project's own install script. Windows: Claude Code's own PowerShell
# installer; OpenCode has none (its script needs bash), so its latest Windows build is
# downloaded from its GitHub releases into the same folder its script uses (~/.opencode/bin).

LINUX_INSTALL = {
    "claude": "curl -fsSL https://claude.ai/install.sh | bash",
    "opencode": "curl -fsSL https://opencode.ai/install | bash",
}
CLAUDE_WINDOWS_INSTALL = "irm https://claude.ai/install.ps1 | iex"
OPENCODE_DOWNLOAD = "https://github.com/anomalyco/opencode/releases/latest/download/"
INSTALL_SIZES = {"claude": "about 350 MB", "opencode": "about 80 MB to download, 210 MB installed"}
SIGN_IN = {"claude": "Next: in the FT Assistant setup window, choose Claude Code and click Save. "
                     "Then say \"{word}, hello\" to sign in with your Claude account.",
           "opencode": "Next: in the FT Assistant setup window, choose OpenCode and click Save. "
                       "Then say \"{word}, hello\" to start it."}


def _has_avx2():
    """Windows: whether the processor has AVX2 (OpenCode's normal build needs it)."""
    try:
        import ctypes
        return bool(ctypes.windll.kernel32.IsProcessorFeaturePresent(40))
    except Exception:
        return False


def opencode_windows_asset(machine=None, avx2=None):
    """Which OpenCode Windows build fits this computer (the same choice its install script makes)."""
    m = (machine or platform.machine()).lower()
    if m in ("arm64", "aarch64"):
        return "opencode-windows-arm64.zip"
    if avx2 is None:
        avx2 = _has_avx2()
    return "opencode-windows-x64.zip" if avx2 else "opencode-windows-x64-baseline.zip"


def _ps_quote(s):
    return "'" + s.replace("'", "''") + "'"


def opencode_windows_script(url):
    """PowerShell that installs OpenCode's Windows build from `url` into ~/.opencode/bin and adds
    that folder to the user's PATH (so `opencode` also works in a new terminal)."""
    return "\n".join([
        "$ErrorActionPreference = 'Stop'; $ProgressPreference = 'SilentlyContinue'",
        "try {",
        "  $dir = Join-Path $env:USERPROFILE '.opencode\\bin'",
        "  $zip = Join-Path $env:TEMP 'opencode-download.zip'",
        "  Write-Host 'Downloading the latest OpenCode (about 80 MB)...'",
        "  if (Get-Command curl.exe -ErrorAction SilentlyContinue) {",
        f"    & curl.exe -fL --progress-bar -o $zip {_ps_quote(url)}",
        "    if ($LASTEXITCODE -ne 0) { throw 'the download failed' }",
        "  } else {",
        f"    Invoke-WebRequest -UseBasicParsing -Uri {_ps_quote(url)} -OutFile $zip",
        "  }",
        "  New-Item -ItemType Directory -Force -Path $dir | Out-Null",
        "  Expand-Archive -LiteralPath $zip -DestinationPath $dir -Force",
        "  Remove-Item -LiteralPath $zip -Force",
        "  $userPath = [Environment]::GetEnvironmentVariable('Path', 'User')",
        "  if (-not (@($userPath -split ';') -contains $dir)) {",
        "    $new = if ($userPath) { $userPath.TrimEnd(';') + ';' + $dir } else { $dir }",
        "    [Environment]::SetEnvironmentVariable('Path', $new, 'User')",
        "  }",
        "  & (Join-Path $dir 'opencode.exe') --version",
        "  Write-Host \"OpenCode is installed in $dir\"",
        "} catch {",
        "  Write-Host ''",
        "  Write-Host \"Installing OpenCode failed: $($_.Exception.Message)\"",
        "}",
    ])


def install_plan(key, windows=sys.platform == "win32"):
    """(where it comes from, for the confirmation question; the command run in its window)."""
    if not windows:
        return f"its official install script:\n\n{LINUX_INSTALL[key]}", LINUX_INSTALL[key]
    if key == "claude":
        return f"its official installer:\n\n{CLAUDE_WINDOWS_INSTALL}", CLAUDE_WINDOWS_INSTALL
    url = OPENCODE_DOWNLOAD + opencode_windows_asset()
    return (f"its latest official Windows release:\n\n{url}\n\ninto your user folder "
            "(.opencode\\bin)", opencode_windows_script(url))


def install_window_command(key, word, windows=sys.platform == "win32", which=shutil.which):
    """The command that opens a visible window installing `key`, ending with what to do next."""
    _, cmd = install_plan(key, windows)
    nxt = SIGN_IN[key].format(word=word)
    if windows:
        ps = f"{cmd}\nWrite-Host ''\nWrite-Host {_ps_quote(nxt)}"
        enc = base64.b64encode(ps.encode("utf-16-le")).decode("ascii")
        return ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-NoExit",
                "-EncodedCommand", enc]
    script = (f"{cmd}; echo; echo {_sh_quote(nxt)}; echo; "
              "read -p 'Press Enter to close this window. '")
    return terminal_command(["bash", "-lc", script], str(config.sessions_dir().parent), which=which)


def _sh_quote(s):
    return "'" + s.replace("'", "'\\''") + "'"
