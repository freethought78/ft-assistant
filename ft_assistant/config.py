"""Settings and per-OS locations.

Settings live in a small JSON file:
  Linux:   ~/.config/ft-assistant/settings.json
  Windows: %APPDATA%\\FT Assistant\\settings.json
FT_ASSISTANT_CONFIG_DIR overrides the folder (used to keep a dev build apart from a real install)."""

import json
import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

IS_WINDOWS = sys.platform == "win32"

HARNESSES = ("claude", "opencode")

# Trigger shapes: {"type": "key", "keysym": "Caps_Lock"} or {"type": "button", "button": 12}
DEFAULT_TRIGGER = {"type": "key", "keysym": "Caps_Lock"}


def config_dir():
    override = os.environ.get("FT_ASSISTANT_CONFIG_DIR")
    if override:
        return Path(override)
    if IS_WINDOWS:
        return Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / "FT Assistant"
    base = os.environ.get("XDG_CONFIG_HOME") or (Path.home() / ".config")
    return Path(base) / "ft-assistant"


def update_url():
    """Testing hook: check this URL instead of GitHub (e.g. a local pretend release)."""
    return os.environ.get("FT_ASSISTANT_UPDATE_URL") or None


def data_dir():
    """Where the installed program, its Python runtime and the Whisper model live."""
    override = os.environ.get("FT_ASSISTANT_DATA_DIR")
    if override:
        return Path(override)
    if IS_WINDOWS:
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "FT Assistant"
    base = os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share")
    return Path(base) / "ft-assistant"


def sessions_dir():
    """Neutral starting folder for every new agent session (never an existing project)."""
    return Path.home() / "FT Assistant sessions"


@dataclass
class Settings:
    harness: str = ""                       # "claude" | "opencode" | "" (not chosen yet)
    trigger: dict = field(default_factory=lambda: dict(DEFAULT_TRIGGER))

    @property
    def harness_chosen(self):
        return self.harness in HARNESSES


def settings_path():
    return config_dir() / "settings.json"


def load():
    """Read settings; unknown or broken values fall back to defaults instead of crashing."""
    s = Settings()
    try:
        data = json.loads(settings_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return s
    if data.get("harness") in HARNESSES:
        s.harness = data["harness"]
    trig = data.get("trigger")
    if isinstance(trig, dict) and (
            (trig.get("type") == "key" and isinstance(trig.get("keysym"), str) and trig["keysym"])
            or (trig.get("type") == "button" and isinstance(trig.get("button"), int)
                and trig["button"] not in (1, 2, 3, 4, 5, 6, 7))):
        s.trigger = {k: trig[k] for k in ("type", "keysym", "button") if k in trig}
    return s


def save(s):
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(asdict(s), indent=2), encoding="utf-8")
    os.replace(tmp, path)
