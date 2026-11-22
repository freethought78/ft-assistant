"""The assistant windows FT Assistant opened, kept across its own restarts (an update, a crash)
so "Assistant, ..." still goes to the open window afterwards instead of opening a second one.

Only window numbers and which assistant they're for: no text, no times. Never beyond the login
session: on Linux the file is in the session's runtime folder (/run/user/..., emptied at
logout); everywhere it's marked with the login session, and a file from another one is ignored.
The app also checks that a remembered window still shows its assistant's title before using it
(window numbers get reused)."""

import json
import os
from pathlib import Path

from . import config


def state_file():
    """Where the windows are kept; each build (installed, dev, branch test) has its own."""
    cfg = config.config_dir()
    run = os.environ.get("XDG_RUNTIME_DIR")
    if not config.IS_WINDOWS and run and Path(run).is_dir():
        return Path(run) / f"{cfg.name}-agent-windows.json"
    return cfg / "agent-windows.json"


def load(path, session):
    """{harness key: window number} saved in this login session, else {}."""
    if not path or not session:
        return {}
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if data.get("session") != session:
            return {}
        return {str(k): int(v) for k, v in data.get("windows", {}).items()}
    except (OSError, ValueError, TypeError, AttributeError):
        return {}


def save(path, session, windows):
    """Keep {harness key: window number}; with none left, remove the file."""
    if not path or not session:
        return
    path = Path(path)
    try:
        if not windows:
            path.unlink(missing_ok=True)
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(json.dumps({"session": session, "windows": windows}), encoding="utf-8")
        os.replace(tmp, path)
    except OSError:
        pass                    # only a convenience: without it a new window opens after a restart
