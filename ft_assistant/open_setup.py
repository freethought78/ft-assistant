"""Open the setup window with the Python that draws the clearest text (see gui.py).
Used by the "FT Assistant setup" menu entry and by the app itself."""

import os
import sys

from .gui import setup_python


def command():
    """(argv, env) that runs the setup window."""
    exe, extra = setup_python()
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join([p for p in [env.get("PYTHONPATH", "")] + extra if p])
    return [exe, "-m", "ft_assistant.setup_ui"], env


if __name__ == "__main__":
    argv, env = command()
    os.execve(argv[0], argv + sys.argv[1:], env)
