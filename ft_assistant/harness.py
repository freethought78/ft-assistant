"""Starting Claude Code / OpenCode in a visible terminal window, and recognising their windows.

Nothing here ever runs an agent in the background: every session is a normal, visible,
interactive terminal window the user can watch and talk to."""

import os
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


def find_exe(h):
    return shutil.which(h.exe)


def terminal_command(argv, folder, which=shutil.which, windows=sys.platform == "win32"):
    """Wrap `argv` so it runs in a new window of the system's default terminal.

    Windows: Windows Terminal (wt) if installed, else the program itself in a new console
    window (see new_window_flags)."""
    if windows:
        exe = which(argv[0]) or argv[0]       # full path (claude.exe / opencode.cmd)
        if which("wt"):
            # wt treats ";" as "next command"; "\;" is a literal semicolon.
            return ["wt", "-d", str(folder), exe] + [a.replace(";", "\\;") for a in argv[1:]]
        return [exe] + argv[1:]
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
    CREATE_NEW_CONSOLE, CREATE_NO_WINDOW = 0x10, 0x08000000
    # wt opens its own window; anything else needs a new console window.
    return {"creationflags": CREATE_NO_WINDOW if cmd[0] == "wt" else CREATE_NEW_CONSOLE}


def open_session(harness_key, prompt, launcher=subprocess.Popen):
    """Open a visible terminal window with the chosen harness in the neutral folder,
    continuing the last conversation there (one ongoing conversation, no build-up)."""
    h = HARNESSES[harness_key]
    if not find_exe(h):
        raise RuntimeError(f"{h.name} isn't installed. Say \"Assistant setup\" to install it.")
    folder = config.sessions_dir()
    folder.mkdir(parents=True, exist_ok=True)
    resume = last_conversation(harness_key, folder)
    cmd = terminal_command(h.argv(folder, prompt, resume), folder)
    launcher(cmd, cwd=str(folder), env=clean_env(), stdin=subprocess.DEVNULL,
             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **new_window_kwargs(cmd))
    return h
