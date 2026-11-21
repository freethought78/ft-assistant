"""Which build is running: a released install, or a test build from a git branch.

A test build is the code from a git checkout, run in place of the installed copy by
`run-branch.sh` (or next to it by `run-dev.sh`). Its version line names the branch and says it
isn't a public release, so it can't be mistaken for the installed version."""

import os
import re
import subprocess
from pathlib import Path

from . import __version__

REPO = Path(__file__).resolve().parent.parent
_cached = None


def _git_branch(repo=REPO):
    """The checked-out branch of the git checkout this code runs from, or None if it isn't one
    (an installed copy). A detached checkout (run-branch.sh's snapshots) has no branch name."""
    if not (repo / ".git").exists():
        return None
    try:
        r = subprocess.run(["git", "-C", str(repo), "branch", "--show-current"],
                           capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return "unknown branch"
    return r.stdout.strip() or "unknown branch"


def branch(env=None, repo=REPO):
    """The branch this test build comes from, or None for a released install.
    FT_ASSISTANT_BUILD (set by run-branch.sh) wins, since its snapshots have no branch name."""
    env = os.environ if env is None else env
    return env.get("FT_ASSISTANT_BUILD") or _git_branch(repo)


def describe(env=None, repo=REPO, version=__version__):
    """The version as shown to the user:
      installed:   "0.2.8"
      test build:  "0.3.0 test build (conversation-management): not a public release"
      from next:   "0.3.0 release candidate (next): not a public release"
    FT_ASSISTANT_BUILD_NOTE (e.g. "with uncommitted changes") is added after the branch."""
    global _cached
    if env is None and repo == REPO and version == __version__ and _cached is not None:
        return _cached
    b = branch(env, repo)
    if not b:
        text = version
    else:
        env_ = os.environ if env is None else env
        base = re.sub(r"\.dev\d+$", "", version)
        kind = "release candidate" if b == "next" else "test build"
        note = env_.get("FT_ASSISTANT_BUILD_NOTE")
        text = f"{base} {kind} ({b}{', ' + note if note else ''}): not a public release"
    if env is None and repo == REPO and version == __version__:
        _cached = text
    return text


def is_test_build(env=None, repo=REPO):
    return branch(env, repo) is not None
