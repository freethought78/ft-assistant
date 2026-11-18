"""Windows layer: Assistant key (low-level hooks), typing (SendInput), window info,
notifications, key capture and the single-instance lock. Same functions as platform_linux.

Only the Python standard library (ctypes) is used. Key names follow the X11 keysym names the
settings file uses on Linux ("Caps_Lock", "F13", "a"), so a settings file means the same thing on
both systems; mouse side buttons are buttons 8 and 9, as on Linux."""

import ctypes
import logging
import os
import queue
import subprocess
import sys
import threading
import time
from ctypes import wintypes

log = logging.getLogger("ft_assistant")

if sys.platform == "win32":
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
else:                      # importable on Linux for the pure parts (unit tests)
    user32 = kernel32 = None

CREATE_NO_WINDOW = 0x08000000
CREATE_NEW_CONSOLE = 0x00000010
CREATE_NEW_PROCESS_GROUP = 0x00000200

# ---------------------------------------------------------------- key names <-> virtual keys

VK = {
    "Caps_Lock": 0x14, "Scroll_Lock": 0x91, "Num_Lock": 0x90, "Pause": 0x13, "Insert": 0x2D,
    "Delete": 0x2E, "Home": 0x24, "End": 0x23, "Prior": 0x21, "Next": 0x22, "Menu": 0x5D,
    "Print": 0x2C, "Escape": 0x1B, "Return": 0x0D, "space": 0x20, "Tab": 0x09,
    "BackSpace": 0x08, "Left": 0x25, "Up": 0x26, "Right": 0x27, "Down": 0x28,
    "Shift_L": 0xA0, "Shift_R": 0xA1, "Control_L": 0xA2, "Control_R": 0xA3,
    "Alt_L": 0xA4, "Alt_R": 0xA5, "Super_L": 0x5B, "Super_R": 0x5C,
}
VK.update({f"F{i}": 0x6F + i for i in range(1, 25)})                 # F1..F24
VK.update({chr(c): 0x41 + c - ord("a") for c in range(ord("a"), ord("z") + 1)})
VK.update({str(d): 0x30 + d for d in range(10)})
VK.update({f"KP_{d}": 0x60 + d for d in range(10)})
VK_NAME = {v: k for k, v in VK.items()}


def vk_for(keysym):
    """Virtual-key code for a key name ("Caps_Lock", "F13", "a", or "VK_0x2a")."""
    if keysym in VK:
        return VK[keysym]
    if keysym.startswith("VK_0x"):
        return int(keysym[5:], 16)
    return None


def name_for(vk):
    return VK_NAME.get(vk, f"VK_0x{vk:02x}")


# Mouse messages -> X-style button numbers (left 1, middle 2, right 3, wheel 4, side 8/9).
WM_KEYDOWN, WM_KEYUP, WM_SYSKEYDOWN, WM_SYSKEYUP = 0x100, 0x101, 0x104, 0x105
WM_LBUTTONDOWN, WM_RBUTTONDOWN, WM_MBUTTONDOWN = 0x201, 0x204, 0x207
WM_MOUSEWHEEL, WM_XBUTTONDOWN, WM_XBUTTONUP, WM_MOUSEHWHEEL = 0x20A, 0x20B, 0x20C, 0x20E
WM_QUIT = 0x0012
WH_KEYBOARD_LL, WH_MOUSE_LL = 13, 14
LLKHF_INJECTED, LLMHF_INJECTED = 0x10, 0x01
_DOWN_BUTTON = {WM_LBUTTONDOWN: 1, WM_MBUTTONDOWN: 2, WM_RBUTTONDOWN: 3, WM_MOUSEWHEEL: 4,
                WM_MOUSEHWHEEL: 6}


def xbutton_number(mouse_data):
    """XBUTTON1 (back) -> 8, XBUTTON2 (forward) -> 9."""
    return 8 if (mouse_data >> 16) & 0xFFFF == 1 else 9


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [("vkCode", wintypes.DWORD), ("scanCode", wintypes.DWORD),
                ("flags", wintypes.DWORD), ("time", wintypes.DWORD),
                ("dwExtraInfo", ctypes.c_size_t)]


class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [("pt", wintypes.POINT), ("mouseData", wintypes.DWORD),
                ("flags", wintypes.DWORD), ("time", wintypes.DWORD),
                ("dwExtraInfo", ctypes.c_size_t)]


LRESULT = ctypes.c_ssize_t
HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM) \
    if sys.platform == "win32" else None


def _setup_hook_types():
    user32.SetWindowsHookExW.restype = wintypes.HHOOK
    user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, wintypes.HINSTANCE, wintypes.DWORD]
    user32.CallNextHookEx.restype = LRESULT
    user32.CallNextHookEx.argtypes = [wintypes.HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
    user32.UnhookWindowsHookEx.argtypes = [wintypes.HHOOK]
    kernel32.GetModuleHandleW.restype = wintypes.HMODULE


def _message_loop():
    msg = wintypes.MSG()
    while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
        user32.TranslateMessage(ctypes.byref(msg))
        user32.DispatchMessageW(ctypes.byref(msg))


def session_problem():
    return None


# ---------------------------------------------------------------- Assistant key

class TriggerListener:
    """Calls on_press/on_release when the Assistant key goes down/up. The key (or side button)
    is swallowed, so it never reaches other programs and Caps Lock never toggles."""

    def __init__(self, trigger, on_press, on_release):
        self.trigger = trigger
        self.on_press = on_press
        self.on_release = on_release
        self.events = queue.Queue()     # hooks must return fast; work happens on another thread
        self.down = False

    def _dispatch(self):
        while True:
            ev = self.events.get()
            if ev == "stop":
                return
            (self.on_press if ev == "down" else self.on_release)()

    def run(self):
        _setup_hook_types()
        is_key = self.trigger["type"] == "key"
        want_vk = vk_for(self.trigger.get("keysym", "")) if is_key else None
        want_btn = self.trigger.get("button")
        if is_key and want_vk is None:
            raise RuntimeError(f"unknown key {self.trigger.get('keysym')!r}")
        threading.Thread(target=self._dispatch, daemon=True).start()

        def on_key(code, wparam, lparam):
            if code == 0:
                k = ctypes.cast(lparam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
                if k.vkCode == want_vk and not k.flags & LLKHF_INJECTED:
                    if wparam in (WM_KEYDOWN, WM_SYSKEYDOWN):
                        if not self.down:                 # ignore auto-repeat
                            self.down = True
                            self.events.put("down")
                    elif wparam in (WM_KEYUP, WM_SYSKEYUP):
                        if self.down:
                            self.down = False
                            self.events.put("up")
                    return 1                              # swallow the key
            return user32.CallNextHookEx(None, code, wparam, lparam)

        def on_mouse(code, wparam, lparam):
            if code == 0 and wparam in (WM_XBUTTONDOWN, WM_XBUTTONUP):
                m = ctypes.cast(lparam, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
                if not m.flags & LLMHF_INJECTED and xbutton_number(m.mouseData) == want_btn:
                    if wparam == WM_XBUTTONDOWN and not self.down:
                        self.down = True
                        self.events.put("down")
                    elif wparam == WM_XBUTTONUP and self.down:
                        self.down = False
                        self.events.put("up")
                    return 1
            return user32.CallNextHookEx(None, code, wparam, lparam)

        self._proc = HOOKPROC(on_key if is_key else on_mouse)     # keep a reference
        hook = user32.SetWindowsHookExW(WH_KEYBOARD_LL if is_key else WH_MOUSE_LL, self._proc,
                                        kernel32.GetModuleHandleW(None), 0)
        if not hook:
            raise RuntimeError("couldn't watch the Assistant key (SetWindowsHookEx failed)")
        self._thread_id = kernel32.GetCurrentThreadId()
        _message_loop()                                  # returns when stop() is called
        user32.UnhookWindowsHookEx(hook)
        self.events.put("stop")

    def stop(self):
        """Stop listening: run() unhooks and returns."""
        user32.PostThreadMessageW(getattr(self, "_thread_id", 0), WM_QUIT, 0, 0)


LOCK_KEYS = {"Num_Lock", "Caps_Lock", "Scroll_Lock"}
last_capture = []
SETTLE = 0.25    # seconds to wait after a lock key for the "real" key that may follow it


def pick_captured(presses):
    """From the key presses seen at the start of a capture, pick the one the user meant.

    Wine sends its own press of each lock key that's on (e.g. Num Lock) just before and after
    the real key, to keep lock states in step: [Num_Lock, Pause, Num_Lock]. So: the first key
    that isn't a lock key wins; if there are only lock keys, the one pressed an odd number of
    times (the real press; the synced ones come in pairs) wins."""
    keys = [trig for _, trig in presses]
    if not keys:
        return None
    for trig in keys:
        if trig.get("keysym") not in LOCK_KEYS:
            return trig
    for trig in keys:
        if keys.count(trig) % 2 == 1:
            return trig
    return keys[0]


def capture_next(timeout=15.0):
    """The next key or mouse button pressed anywhere, as a trigger dict, or None on timeout."""
    _setup_hook_types()
    presses = []                     # (time, trigger) in arrival order
    thread_id = {}
    first = threading.Event()

    def add(trig):
        presses.append((time.monotonic(), trig))
        first.set()

    def on_key(code, wparam, lparam):
        if code == 0 and wparam in (WM_KEYDOWN, WM_SYSKEYDOWN):
            k = ctypes.cast(lparam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
            if not k.flags & LLKHF_INJECTED:
                add({"type": "key", "keysym": name_for(k.vkCode)})
        return user32.CallNextHookEx(None, code, wparam, lparam)

    def on_mouse(code, wparam, lparam):
        if code == 0:
            m = ctypes.cast(lparam, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
            if not m.flags & LLMHF_INJECTED:
                if wparam == WM_XBUTTONDOWN:
                    add({"type": "button", "button": xbutton_number(m.mouseData)})
                elif wparam in _DOWN_BUTTON:
                    add({"type": "button", "button": _DOWN_BUTTON[wparam]})
        return user32.CallNextHookEx(None, code, wparam, lparam)

    def run():
        thread_id["id"] = kernel32.GetCurrentThreadId()
        kp, mp = HOOKPROC(on_key), HOOKPROC(on_mouse)
        mod = kernel32.GetModuleHandleW(None)
        hooks = [user32.SetWindowsHookExW(WH_KEYBOARD_LL, kp, mod, 0),
                 user32.SetWindowsHookExW(WH_MOUSE_LL, mp, mod, 0)]
        started.set()
        _message_loop()
        for h in hooks:
            if h:
                user32.UnhookWindowsHookEx(h)

    started = threading.Event()
    t = threading.Thread(target=run, daemon=True)
    t.start()
    started.wait(5)
    if first.wait(timeout):
        time.sleep(SETTLE + 0.05)    # let a real key that follows a lock key arrive
    user32.PostThreadMessageW(thread_id.get("id", 0), WM_QUIT, 0, 0)
    t.join(2)
    global last_capture
    last_capture = list(presses)        # for diagnosing odd keyboards
    trig = pick_captured(last_capture)
    if trig and trig.get("keysym") == "Caps_Lock":
        caps_lock_off()                 # pressing it to choose it toggled it on
    return trig


# ---------------------------------------------------------------- typing

class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                ("dwExtraInfo", ctypes.c_size_t)]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]


INPUT_KEYBOARD, KEYEVENTF_KEYUP, KEYEVENTF_UNICODE = 1, 0x0002, 0x0004


def key_events(text):
    """(vk, scan, flags) tuples that type `text`: Unicode characters, Enter for new lines."""
    out = []
    for ch in text.replace("\r\n", "\n"):
        if ch == "\n":
            out += [(0x0D, 0, 0), (0x0D, 0, KEYEVENTF_KEYUP)]
            continue
        data = ch.encode("utf-16-le")
        for i in range(0, len(data), 2):            # characters outside the BMP: two units
            unit = int.from_bytes(data[i:i + 2], "little")
            out += [(0, unit, KEYEVENTF_UNICODE), (0, unit, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP)]
    return out


def _send(events):
    arr = (INPUT * len(events))()
    for i, (vk, scan, flags) in enumerate(events):
        arr[i].type = INPUT_KEYBOARD
        arr[i].u.ki = KEYBDINPUT(vk, scan, flags, 0, 0)
    user32.SendInput(len(events), arr, ctypes.sizeof(INPUT))


def type_text(text):
    _send(key_events(text))


def press_enter():
    _send([(0x0D, 0, 0), (0x0D, 0, KEYEVENTF_KEYUP)])


def caps_lock_off():
    if user32.GetKeyState(0x14) & 1:
        _send([(0x14, 0, 0), (0x14, 0, KEYEVENTF_KEYUP)])   # injected: our hook ignores it


# ---------------------------------------------------------------- windows

TERMINAL_CLASSES = {"cascadia_hosting_window_class",   # Windows Terminal
                    "consolewindowclass",              # classic console
                    "mintty", "virtualconsoleclass"}


def window_info(hwnd):
    buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buf, 256)
    cls = buf.value.lower()
    n = user32.GetWindowTextLengthW(hwnd)
    t = ctypes.create_unicode_buffer(n + 1)
    user32.GetWindowTextW(hwnd, t, n + 1)
    return cls, t.value


def active_window():
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return None, "", ""
    cls, title = window_info(hwnd)
    return int(hwnd), cls, title


def terminal_windows():
    found = set()
    ENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def cb(hwnd, _):
        if user32.IsWindowVisible(hwnd) and window_info(hwnd)[0] in TERMINAL_CLASSES:
            found.add(int(hwnd))
        return True
    user32.EnumWindows(ENUMPROC(cb), 0)
    return found


def is_terminal_class(cls):
    return (cls or "").lower() in TERMINAL_CLASSES


def activate_window(hwnd):
    """Bring a window to the front. Windows only lets the active program do that, so a tap of
    Alt (injected, ignored by our hook) is sent first, the usual way around it."""
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, 9)               # SW_RESTORE
    _send([(0x12, 0, 0), (0x12, 0, KEYEVENTF_KEYUP)])
    user32.SetForegroundWindow(hwnd)
    return int(user32.GetForegroundWindow() or 0) == int(hwnd)


# ---------------------------------------------------------------- notifications

_TOAST = (
    "$t=[Windows.UI.Notifications.ToastNotificationManager,Windows.UI.Notifications,"
    "ContentType=WindowsRuntime];"
    "$c=$t::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02);"
    "$n=$c.GetElementsByTagName('text');"
    "[void]$n.Item(0).AppendChild($c.CreateTextNode($env:FT_TITLE));"
    "[void]$n.Item(1).AppendChild($c.CreateTextNode($env:FT_MSG));"
    "$t::CreateToastNotifier('{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\\WindowsPowerShell\\v1.0\\"
    "powershell.exe').Show([Windows.UI.Notifications.ToastNotification]::new($c))")


def notify(msg, title="FT Assistant"):
    """A Windows toast (never steals focus). Uses Windows PowerShell 5.1, which can reach the
    toast API; if that fails nothing is shown."""
    env = dict(os.environ, FT_TITLE=title, FT_MSG=msg)
    try:
        subprocess.Popen(["powershell", "-NoProfile", "-NonInteractive", "-Command", _TOAST],
                         env=env, creationflags=CREATE_NO_WINDOW,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        pass


def notify_with_action(msg, action_label, on_click, title="FT Assistant"):
    """Clicking a toast needs a registered app identity, which a plain script doesn't have yet,
    so on Windows the toast only tells the user what to say."""
    notify(msg, title)


# ---------------------------------------------------------------- processes and locking

def lock_single_instance(path):
    import msvcrt
    f = open(path, "a+")
    f.seek(0)
    try:
        msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        f.close()
        return None
    f.seek(0)
    f.truncate()
    f.write(str(os.getpid()))
    f.flush()
    return f


def popen_detached_kwargs():
    return {"creationflags": CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP}
