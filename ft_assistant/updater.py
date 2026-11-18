"""Update check against the project's latest GitHub Release.

- One request to GitHub's public "latest release" API: no account, no user data.
- Offline or no answer: give up silently and try again next time.
- Never downloads anything by itself; the user decides on the setup screen.

Reminder rule per version: tell the user once; if they don't update, one more reminder after
REMIND_AFTER; after that stay quiet about that version (a newer release starts over)."""

import json
import re
import time
import urllib.request
from dataclasses import dataclass

from . import __version__, config

# The project's home on GitHub (the user's freethought78 account; never ftftft78).
GITHUB_REPO = "freethought78/ft-assistant"
API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"

CHECK_EVERY = 24 * 3600          # at most one automatic check per day
REMIND_AFTER = 3 * 24 * 3600     # "Not now" -> quiet for a few days, then one reminder
TIMEOUT = 10


@dataclass(frozen=True)
class Release:
    version: str
    notes: str
    url: str


# ---------------------------------------------------------------- versions

def parse_version(v):
    """'v1.2.3' -> (1, 2, 3, 1); '0.1.0.dev0' -> (0, 1, 0, 0). Pre-releases sort first."""
    v = (v or "").strip().lstrip("vV")
    m = re.match(r"^(\d+(?:\.\d+)*)(.*)$", v)
    if not m:
        return None
    nums = [int(x) for x in m.group(1).split(".")]
    nums += [0] * (3 - len(nums))
    final = 0 if m.group(2).strip(".-") else 1     # anything after the numbers = pre-release
    return tuple(nums[:3]) + (final,)


def is_newer(candidate, current=__version__):
    a, b = parse_version(candidate), parse_version(current)
    return a is not None and b is not None and a > b


# ---------------------------------------------------------------- remembered state

def _state_path():
    return config.config_dir() / "update-state.json"


def load_state():
    try:
        return json.loads(_state_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_state(state):
    p = _state_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, indent=2), encoding="utf-8")


def due_for_check(state, now=None):
    now = time.time() if now is None else now
    if "last_check" not in state:
        return True
    return now - state["last_check"] >= CHECK_EVERY


def should_notify(release, state, now=None):
    """Tell the user about `release` now? (once, then one reminder after REMIND_AFTER)"""
    now = time.time() if now is None else now
    if release is None or not is_newer(release.version):
        return False
    seen = state.get("notified", {}).get(release.version)
    if not seen:
        return True
    return seen.get("count", 0) < 2 and now - seen.get("last", 0) >= REMIND_AFTER


def mark_notified(state, version, now=None):
    now = time.time() if now is None else now
    seen = state.setdefault("notified", {}).setdefault(version, {"count": 0, "last": 0})
    seen["count"] += 1
    seen["last"] = now
    state["notified"] = {version: seen}           # forget older versions


def mark_not_now(state, version, now=None):
    """User chose "Not now" on the setup screen: quiet for REMIND_AFTER, then one reminder."""
    now = time.time() if now is None else now
    state["notified"] = {version: {"count": 1, "last": now}}


# ---------------------------------------------------------------- the check

def parse_release(data):
    tag = data.get("tag_name") or data.get("name") or ""
    if not parse_version(tag) or data.get("draft") or data.get("prerelease"):
        return None
    return Release(tag.lstrip("vV"), (data.get("body") or "").strip(), data.get("html_url") or "")


def fetch_latest(url=None):
    """The latest release, or None if offline / not reachable / nothing usable."""
    url = url or config.update_url() or API_URL
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json",
                                               "User-Agent": "FT-Assistant-updater"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return parse_release(json.loads(r.read().decode("utf-8")))
    except Exception:
        return None


def check(now=None):
    """Run one check, remember when, and return the newer release if there is one."""
    now = time.time() if now is None else now
    state = load_state()
    rel = fetch_latest()
    state["last_check"] = now
    if rel is not None:
        state["latest"] = {"version": rel.version, "notes": rel.notes, "url": rel.url}
    save_state(state)
    return rel if rel is not None and is_newer(rel.version) else None


def check_now(now=None):
    """For the setup screen's button: ("update", release) | ("latest", None) | ("unreachable", None)."""
    now = time.time() if now is None else now
    state = load_state()
    rel = fetch_latest()
    state["last_check"] = now
    if rel is None:
        save_state(state)
        return "unreachable", None
    state["latest"] = {"version": rel.version, "notes": rel.notes, "url": rel.url}
    save_state(state)
    return ("update", rel) if is_newer(rel.version) else ("latest", None)


def known_update():
    """The newer release found by the last check, if any (for the setup screen)."""
    latest = load_state().get("latest")
    if latest and is_newer(latest.get("version", "")):
        return Release(latest["version"], latest.get("notes", ""), latest.get("url", ""))
    return None
