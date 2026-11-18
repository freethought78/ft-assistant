"""The platform layer for this computer: Linux (X11) or Windows. Both modules offer the same
functions (Assistant key listener, typing, window info, notifications, key capture, locking)."""

import sys

if sys.platform == "win32":
    from .platform_windows import *  # noqa: F401,F403
else:
    from .platform_linux import *  # noqa: F401,F403
