"""The names FT Assistant's running processes show (Task Manager, System Monitor, top, ps, pgrep),
instead of "python" or "pythonw", so users and FT Assistant itself can find and close them.

- Linux: each process sets its own name at start (prctl PR_SET_NAME, at most 15 characters):
  `pgrep -x "FT Assistant"` finds the program.
- Windows: a program's name comes from its .exe file, so the installer makes copies of FT
  Assistant's own pythonw.exe under these names (with "FT Assistant" as their description,
  which Task Manager shows), in the same folder; the processes are started with those.

Also imported on its own by whisper_worker.py (which runs as a script from this folder)."""

import sys
from pathlib import Path

ROLES = ("app", "speech", "setup", "help")
LINUX_NAMES = {"app": "FT Assistant", "speech": "FT Asst speech", "setup": "FT Asst setup",
               "help": "FT Asst help"}
WINDOWS_EXES = {"app": "FT Assistant.exe", "speech": "FT Assistant speech.exe",
                "setup": "FT Assistant setup.exe", "help": "FT Assistant help.exe"}


def set_name(role):
    """Linux: this process's name becomes the role's name. Never fails."""
    if not sys.platform.startswith("linux"):
        return
    try:
        import ctypes
        libc = ctypes.CDLL(None)
        libc.prctl(15, LINUX_NAMES[role].encode()[:15], 0, 0, 0)       # 15 = PR_SET_NAME
    except Exception:
        pass


def executable(role, current=None, windows=sys.platform == "win32"):
    """The program to start a `role` process with: on Windows the named copy next to the running
    Python, if the installer made it; otherwise this Python itself."""
    exe = Path(current or sys.executable)
    if windows:
        named = exe.with_name(WINDOWS_EXES[role])
        if named.exists():
            return str(named)
    return str(exe)
