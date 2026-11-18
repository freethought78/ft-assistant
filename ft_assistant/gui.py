"""Which Python shows the setup window.

The standalone Python the installer downloads has a Tk that, on Linux, can only use old X11
fonts (no smoothing). The computer's own Python with the system Tk package (python3-tk) draws
smooth desktop fonts, so on Linux the setup window uses that one when it can, and falls back to
the bundled Python otherwise. On Windows the bundled Tk already uses Windows' smooth fonts."""

import shutil
import subprocess
import sys
from pathlib import Path

from . import config

PROBE = ("import sys, tkinter\n"
         "assert sys.version_info >= (3, 8)\n"
         "r = tkinter.Tk(); r.withdraw()\n"
         "print(r.tk.call('::tk::pkgconfig', 'get', 'fontsystem'))")

_cached = None


def draws_smooth_fonts(exe):
    """True if this Python's Tk uses the desktop's smooth (Xft) fonts."""
    if not exe:
        return False
    try:
        r = subprocess.run([exe, "-I", "-c", PROBE], capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.SubprocessError):
        return False
    return r.returncode == 0 and r.stdout.strip() == "xft"


def vendor_dir():
    """A folder with the small pure-Python packages the setup window needs (python-xlib and
    six), copied from our own Python so the system Python can use them."""
    import six
    import Xlib
    dest = config.config_dir() / "vendor"
    stamp = dest / "VERSION"
    want = f"Xlib {Xlib.__version__} six {six.__version__}"
    try:
        if stamp.read_text() == want:
            return dest
    except OSError:
        pass
    shutil.rmtree(dest, ignore_errors=True)
    dest.mkdir(parents=True)
    shutil.copytree(Path(Xlib.__file__).parent, dest / "Xlib",
                    ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copyfile(six.__file__, dest / "six.py")
    stamp.write_text(want)
    return dest


def setup_python():
    """(python executable, extra folders for PYTHONPATH) to run the setup window with."""
    global _cached
    if _cached is None:
        if sys.platform == "win32" or draws_smooth_fonts(sys.executable):
            _cached = (sys.executable, [])
        else:
            system = shutil.which("python3", path="/usr/bin:/bin:/usr/local/bin")
            if system and draws_smooth_fonts(system):
                _cached = (system, [str(vendor_dir())])
            else:
                _cached = (sys.executable, [])
    return _cached
