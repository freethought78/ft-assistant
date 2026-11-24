"""Linux (X11) layer: watching the Assistant key, typing text, window info, notifications.

Wayland isn't supported yet (it needs a different key-capture and typing method)."""

import contextlib
import ctypes
import ctypes.util
import functools
import logging
import os
import subprocess
import threading
import time

from Xlib import X, XK, display
from Xlib.ext import record
from Xlib.protocol import rq

log = logging.getLogger("ft_assistant")

# Window classes of common terminal programs (lowercase).
TERMINAL_CLASSES = {"gnome-terminal-server", "gnome-terminal", "xterm", "uxterm", "konsole",
                    "xfce4-terminal", "mate-terminal", "tilix", "kitty", "alacritty",
                    "terminator", "lxterminal", "qterminal", "x-terminal-emulator", "wezterm",
                    "org.wezfurlong.wezterm", "foot", "ghostty", "com.mitchellh.ghostty"}


def session_problem():
    """Return a message if this desktop session can't be supported, else None."""
    if os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland" or (
            os.environ.get("WAYLAND_DISPLAY") and not os.environ.get("DISPLAY")):
        return ("FT Assistant needs an X11 desktop session. Wayland isn't supported yet; "
                "choose an X11 (\"Xorg\") session at the login screen.")
    if not os.environ.get("DISPLAY"):
        return "No X11 display found."
    return None


# ---------------------------------------------------------------- Assistant key

# ---- "<word> undo": was anything typed or clicked since FT Assistant typed?
# Only a count of the user's key presses and clicks, in memory: never which keys, never saved or
# logged. FT Assistant's own typing (xdotool) isn't counted: it looks the same to X, so presses
# are ignored while it types and for a moment after (SYNTH_GRACE).
SYNTH_GRACE = 0.3
SCROLL_BUTTONS = {4, 5, 6, 7}         # the wheel isn't a click
_input = {"count": 0, "quiet_until": 0.0, "listening": False}


def input_watch_ok():
    """True while the listener records keys and buttons, so input_count() can be trusted."""
    return _input["listening"]


def input_count():
    """How many keys and mouse buttons the user has pressed (not the Assistant key, not
    FT Assistant's own typing) since FT Assistant started."""
    return _input["count"]


def _user_input():
    if time.monotonic() >= _input["quiet_until"]:
        _input["count"] += 1


@contextlib.contextmanager
def _synthesizing():
    _input["quiet_until"] = float("inf")
    try:
        yield
    finally:
        _input["quiet_until"] = time.monotonic() + SYNTH_GRACE


class TriggerListener:
    """Calls on_press/on_release when the Assistant key (keyboard key or extra mouse button)
    goes down/up. Keyboard keys are also grabbed so the key itself never reaches other apps."""

    def __init__(self, trigger, on_press, on_release):
        self.trigger = trigger
        self.on_press = on_press
        self.on_release = on_release
        self._ignore = threading.Event()   # set while we synthesize keys ourselves
        self.keycode = None
        self._grab_dpy = None

    def _resolve(self, dpy):
        if self.trigger["type"] == "key":
            sym = XK.string_to_keysym(self.trigger["keysym"])
            code = dpy.keysym_to_keycode(sym) if sym else 0
            if not code:
                raise RuntimeError(f"key {self.trigger['keysym']!r} isn't on this keyboard")
            self.keycode = code

    def _grab_key(self):
        """Grab the key on the root window so apps don't receive it (any modifiers)."""
        d = display.Display()
        root = d.screen().root
        errors = []
        root.grab_key(self.keycode, X.AnyModifier, True, X.GrabModeAsync, X.GrabModeAsync,
                      onerror=lambda *a: errors.append(a))
        d.sync()
        if errors:
            log.warning("could not grab the Assistant key (another program uses it); "
                        "it will still work but the key also reaches other apps")
        self._grab_dpy = d

        def drain():  # grabbed events must be read or they queue up
            while True:
                try:
                    d.next_event()
                except Exception:
                    return
        threading.Thread(target=drain, daemon=True).start()

    def run(self):
        """Blocks forever, dispatching press/release events."""
        rdpy = display.Display()
        self._resolve(rdpy)
        if self.keycode is not None:
            self._grab_key()
        is_key = self.trigger["type"] == "key"
        events = (X.KeyPress, X.KeyRelease) if is_key else (X.ButtonPress, X.ButtonRelease)
        want = self.keycode if is_key else self.trigger["button"]
        # Every key and button (KeyPress..ButtonRelease): the Assistant key's, and the others
        # only counted for "<word> undo" (input_count).
        ctx = rdpy.record_create_context(0, [record.AllClients], [{
            "core_requests": (0, 0), "core_replies": (0, 0),
            "ext_requests": (0, 0, 0, 0), "ext_replies": (0, 0, 0, 0),
            "delivered_events": (0, 0), "device_events": (X.KeyPress, X.ButtonRelease),
            "errors": (0, 0), "client_started": False, "client_died": False,
        }])

        # Holding a keyboard key makes X send auto-repeat release/press pairs. A real release is
        # only reported if no press follows within REPEAT_GAP seconds.
        REPEAT_GAP = 0.06
        pending = {"timer": None}

        def fire_release():
            pending["timer"] = None
            self.on_release()

        def callback(reply):
            if reply.category != record.FromServer or reply.client_swapped:
                return
            data = reply.data
            while data:
                ev, data = rq.EventField(None).parse_binary_value(data, rdpy.display, None, None)
                if ev.type not in events or ev.detail != want:
                    if ev.type == X.KeyPress or (ev.type == X.ButtonPress
                                                 and ev.detail not in SCROLL_BUTTONS):
                        _user_input()
                    continue
                if self._ignore.is_set():
                    continue
                if ev.type in (X.KeyPress, X.ButtonPress):
                    if pending["timer"] is not None:      # auto-repeat: still held
                        pending["timer"].cancel()
                        pending["timer"] = None
                        continue
                    self.on_press()
                elif ev.type == X.ButtonRelease:
                    self.on_release()
                elif ev.type == X.KeyRelease:
                    t = threading.Timer(REPEAT_GAP, fire_release)
                    pending["timer"] = t
                    t.start()

        self._ctx = ctx
        _input["listening"] = True
        try:
            rdpy.record_enable_context(ctx, callback)   # returns when stop() is called
        finally:
            _input["listening"] = False
        rdpy.record_free_context(ctx)
        rdpy.close()

    def stop(self):
        """Stop listening (run() returns) and release the key grab."""
        try:
            c = display.Display()
            c.record_disable_context(self._ctx)
            c.flush()
            c.close()
        except Exception:
            log.exception("stopping the key listener")
        if self._grab_dpy is not None:
            try:
                self._grab_dpy.close()          # closing the connection ends the grab
            except Exception:
                pass


# ---------------------------------------------------------------- Caps Lock

class _XkbLock:
    """Turns Caps Lock off through XKB directly (no fake key presses)."""
    XkbUseCoreKbd = 0x0100
    LockMask = 1 << 1

    def __init__(self):
        lib = ctypes.util.find_library("X11")
        self.x11 = ctypes.cdll.LoadLibrary(lib) if lib else None
        if self.x11:
            self.x11.XOpenDisplay.restype = ctypes.c_void_p
            self.x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
            self.x11.XkbLockModifiers.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_uint,
                                                  ctypes.c_uint]
            self.x11.XkbGetIndicatorState.argtypes = [ctypes.c_void_p, ctypes.c_uint,
                                                      ctypes.POINTER(ctypes.c_uint)]
            self.x11.XFlush.argtypes = [ctypes.c_void_p]
            self.dpy = self.x11.XOpenDisplay(None)

    def caps_on(self):
        if not (self.x11 and self.dpy):
            return False
        state = ctypes.c_uint(0)
        self.x11.XkbGetIndicatorState(self.dpy, self.XkbUseCoreKbd, ctypes.byref(state))
        return bool(state.value & 1)      # indicator 0 is Caps Lock on standard layouts

    def off(self):
        if self.x11 and self.dpy:
            self.x11.XkbLockModifiers(self.dpy, self.XkbUseCoreKbd, self.LockMask, 0)
            self.x11.XFlush(self.dpy)


_xkb = None


def caps_lock_off():
    global _xkb
    if _xkb is None:
        _xkb = _XkbLock()
    _xkb.off()


# ---------------------------------------------------------------- typing and windows

def type_text(text):
    with _synthesizing():
        subprocess.run(["xdotool", "type", "--clearmodifiers", "--delay", "4", "--", text])


def press_enter():
    with _synthesizing():
        subprocess.run(["xdotool", "key", "--clearmodifiers", "Return"])


def press_escape():
    with _synthesizing():
        subprocess.run(["xdotool", "key", "--clearmodifiers", "Escape"])


def press_backspace(times):
    """Backspace `times` times ("<word> undo")."""
    with _synthesizing():
        subprocess.run(["xdotool", "key", "--clearmodifiers", "--delay", "4",
                        "--repeat", str(int(times)), "BackSpace"])


def activate_window(wid):
    """Bring a window to the front and give it the keyboard. True if it worked."""
    try:
        r = subprocess.run(["xdotool", "windowactivate", "--sync", str(wid)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
    except subprocess.TimeoutExpired:
        return False
    return r.returncode == 0


_wdpy = None
_wlock = threading.Lock()


def _prop(win, name, kind):
    d = _wdpy
    p = win.get_full_property(d.intern_atom(name), kind)
    return p.value if p else None


def window_info(wid):
    """(class_lowercase, title) for a window id."""
    w = _wdpy.create_resource_object("window", wid)
    try:
        cls = w.get_wm_class() or ("", "")
        title = _prop(w, "_NET_WM_NAME", _wdpy.intern_atom("UTF8_STRING")) or w.get_wm_name() or ""
        if isinstance(title, bytes):
            title = title.decode("utf-8", "replace")
        return (cls[-1] or "").lower(), title
    except Exception:
        return "", ""


def _contains(rect, x, y):
    rx, ry, rw, rh = rect
    return rx <= x < rx + rw and ry <= y < ry + rh


def _intersect(a, b):
    x1, y1 = max(a[0], b[0]), max(a[1], b[1])
    x2, y2 = min(a[0] + a[2], b[0] + b[2]), min(a[1] + a[3], b[1] + b[3])
    return (x1, y1, x2 - x1, y2 - y1) if x2 > x1 and y2 > y1 else None


def work_area(x, y):
    """(left, top, width, height) of the usable part (without panels) of the monitor at x, y,
    or None if unknown. Each monitor counts on its own: with monitors of different heights the
    desktop's combined work area is taller than the smaller monitor."""
    try:
        d = display.Display()
    except Exception:
        return None
    try:
        root = d.screen().root

        def prop(name):
            p = root.get_full_property(d.intern_atom(name), X.AnyPropertyType)
            return list(p.value) if p else None

        desk = (prop("_NET_CURRENT_DESKTOP") or [0])[0]
        # Per-monitor work areas, published by GNOME-family desktops (Cinnamon, GNOME, MATE)
        vals = prop(f"_GTK_WORKAREAS_D{desk}")
        rects = [tuple(vals[i:i + 4]) for i in range(0, len(vals or []) - 3, 4)]
        for r in rects:
            if _contains(r, x, y):
                return r
        # Otherwise: the monitor at x, y, minus the desktop's (combined) work area
        monitor = None
        try:
            from Xlib.ext import randr
            for m in randr.get_monitors(root).monitors:
                r = (m.x, m.y, m.width_in_pixels, m.height_in_pixels)
                if _contains(r, x, y):
                    monitor = r
        except Exception:
            pass
        wa = prop("_NET_WORKAREA")
        combined = tuple(wa[4 * desk:4 * desk + 4]) if wa and len(wa) >= 4 * desk + 4 else None
        if monitor and combined:
            return _intersect(monitor, combined) or monitor
        return monitor or combined
    except Exception:
        return None
    finally:
        d.close()


def active_window():
    """(window id, class_lowercase, title) of the focused window, or (None, "", "")."""
    global _wdpy
    with _wlock:
        if _wdpy is None:
            _wdpy = display.Display()
        root = _wdpy.screen().root
        val = _prop(root, "_NET_ACTIVE_WINDOW", X.AnyPropertyType)
        if not val or not val[0]:
            return None, "", ""
        wid = int(val[0])
        cls, title = window_info(wid)
        return wid, cls, title


def terminal_windows():
    """Ids of all open terminal windows."""
    global _wdpy
    with _wlock:
        if _wdpy is None:
            _wdpy = display.Display()
        val = _prop(_wdpy.screen().root, "_NET_CLIENT_LIST", X.AnyPropertyType) or []
        return {int(w) for w in val if window_info(int(w))[0] in TERMINAL_CLASSES}


def is_terminal_class(cls):
    return (cls or "").lower() in TERMINAL_CLASSES


def processes_in(folder):
    """Ids of the processes running in `folder` (to see that an agent started there, also when
    its terminal opened it as a tab instead of a new window)."""
    folder = os.path.realpath(folder)
    out = set()
    for name in os.listdir("/proc"):
        if name.isdigit():
            try:
                if os.readlink(f"/proc/{name}/cwd") == folder:
                    out.add(int(name))
            except OSError:
                pass
    return out


def window_title(wid):
    """The window's current title ("" if it's gone)."""
    global _wdpy
    with _wlock:
        if _wdpy is None:
            _wdpy = display.Display()
        return window_info(int(wid))[1]


def login_session():
    """An id for this login session (boot, login and X display), or None if unknown."""
    try:
        boot = open("/proc/sys/kernel/random/boot_id", encoding="ascii").read().strip()
    except OSError:
        return None
    return f"{boot}/{os.environ.get('XDG_SESSION_ID', '')}/{os.environ.get('DISPLAY', '')}"


def notify(msg, title="FT Assistant"):
    subprocess.Popen(["notify-send", "-a", "FT Assistant", "-t", "4000", title, msg],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def notify_with_action(msg, action_label, on_click, title="FT Assistant"):
    """A normal notification (never steals focus) with one button; `on_click` runs if the
    user clicks it. Waits in a background thread."""
    def run():
        try:
            r = subprocess.run(["notify-send", "-a", "FT Assistant", "-t", "15000",
                                "-A", f"open={action_label}", title, msg],
                               capture_output=True, text=True, timeout=24 * 3600)
        except Exception:
            return
        if r.stdout.strip() == "open":
            on_click()
    threading.Thread(target=run, daemon=True).start()


# ---------------------------------------------------------------- key capture (setup screen)

@functools.lru_cache(maxsize=1)
def _keysym_names():
    for group in ("xf86", "xkb"):
        try:
            XK.load_keysym_group(group)
        except Exception:
            pass
    names = {}
    for k, v in vars(XK).items():
        if k.startswith("XK_") and isinstance(v, int):
            names.setdefault(v, k[3:])
    return names


def capture_next(timeout=15.0):
    """Wait for the next key press or mouse button press anywhere on the screen.

    Returns {"type": "key", "keysym": name} or {"type": "button", "button": n}, or None on
    timeout. Nothing is grabbed, so the press also reaches the focused window."""
    rdpy = display.Display()
    cdpy = display.Display()
    ctx = rdpy.record_create_context(0, [record.AllClients], [{
        "core_requests": (0, 0), "core_replies": (0, 0),
        "ext_requests": (0, 0, 0, 0), "ext_replies": (0, 0, 0, 0),
        "delivered_events": (0, 0), "device_events": (X.KeyPress, X.ButtonPress),
        "errors": (0, 0), "client_started": False, "client_died": False,
    }])
    result = {}
    done = threading.Event()

    def callback(reply):
        if done.is_set() or reply.category != record.FromServer or reply.client_swapped:
            return
        data = reply.data
        while data and not done.is_set():
            ev, data = rq.EventField(None).parse_binary_value(data, rdpy.display, None, None)
            if ev.type == X.ButtonPress:
                result["t"] = {"type": "button", "button": int(ev.detail)}
            elif ev.type == X.KeyPress:
                sym = rdpy.keycode_to_keysym(ev.detail, 0)
                name = _keysym_names().get(sym)
                if not name:
                    continue                      # unknown key: keep waiting
                result["t"] = {"type": "key", "keysym": name}
            done.set()

    t = threading.Thread(target=lambda: rdpy.record_enable_context(ctx, callback), daemon=True)
    t.start()
    done.wait(timeout)
    done.set()
    try:
        cdpy.record_disable_context(ctx)
        cdpy.flush()
        t.join(2)
        cdpy.record_free_context(ctx)
        cdpy.close()
    except Exception:
        pass
    trig = result.get("t")
    if trig and trig.get("keysym") == "Caps_Lock":
        caps_lock_off()                           # pressing it to choose it toggled it on
    return trig


# ---------------------------------------------------------------- single instance

def lock_single_instance(path):
    """Hold an exclusive lock on `path` (and write our process id in it, so the installer can
    stop us). Returns the open file to keep, or None if another copy already holds it."""
    import fcntl
    f = open(path, "a+")
    try:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        f.close()
        return None
    f.seek(0)
    f.truncate()
    f.write(str(os.getpid()))
    f.flush()
    return f


def popen_detached_kwargs():
    """subprocess.Popen options for a program that should outlive us in its own session."""
    return {"start_new_session": True}
