"""Open the setup window. Used by the "FT Assistant setup" menu entry and by the app itself.

It runs with FT Assistant's own Python, like the rest of the program. (Before 0.3.0 the setup
window on Linux borrowed the computer's Python, whose Tk drew smoother text; setup now gives
FT Assistant's own Python a Tk with smooth fonts instead.)"""

import os
import sys

from . import procname


def command():
    """(argv, env) that runs the setup window."""
    return [procname.executable("setup"), "-m", "ft_assistant.setup_ui"], dict(os.environ)


if __name__ == "__main__":
    argv, env = command()
    os.execve(argv[0], argv + sys.argv[1:], env)
