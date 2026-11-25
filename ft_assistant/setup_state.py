"""While the setup screen is open, it tells the running FT Assistant which Assistant key it shows
and whether "Change key" is waiting for a key press (the user's request, 2026-11-25):

- The Assistant key keeps working while setup is open (it used to pause), and a newly chosen key
  works right away, before Save, so it can be tried. Cancel goes back to the saved key.
- It pauses only while "Change key" waits for the new key, so pressing the old one there doesn't
  also start a dictation.

A small file in the settings folder, so it works however setup was opened (by voice or from the
menu). It holds only the key and the setup screen's process id, and setup removes it when it
closes. A file left by a setup that crashed is ignored: its process isn't a running setup screen."""

import json
import os

from . import config

FILE = "setup-open.json"


def path():
    return config.config_dir() / FILE


def write(trigger, capturing):
    """Called by the setup screen whenever its key or "Change key" changes."""
    p = path()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_name(FILE + ".tmp")
        tmp.write_text(json.dumps({"pid": os.getpid(), "trigger": trigger,
                                   "capturing": bool(capturing)}), encoding="utf-8")
        os.replace(tmp, p)
    except OSError:
        pass                    # then the key just keeps its saved setting


def clear():
    """Called when the setup screen closes (only its own file)."""
    p = path()
    try:
        if json.loads(p.read_text(encoding="utf-8")).get("pid") == os.getpid():
            p.unlink()
    except (OSError, ValueError, AttributeError):
        pass


def read(running=None):
    """{"trigger": ..., "capturing": bool} while a setup screen is open, else None."""
    if running is None:
        from . import plat
        running = plat.setup_running
    try:
        data = json.loads(path().read_text(encoding="utf-8"))
        pid = int(data["pid"])
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if not running(pid):
        return None
    trigger = config.valid_trigger(data.get("trigger"))
    return {"trigger": trigger, "capturing": bool(data.get("capturing"))} if trigger else None
