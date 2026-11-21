"""The setup screen ("Assistant setup").

Run as its own process (python -m ft_assistant.setup_ui) so the main app keeps running.
Exit code 10 means settings were saved and changed; 0 means nothing changed."""

import queue
import subprocess
import sys
import threading
import time
import tkinter as tk
import webbrowser
from tkinter import font as tkfont
from tkinter import messagebox, ttk

from . import __version__, buildinfo, config, harness, keys, look, textproc, updater
from . import plat

CHANGED = 10
CAPTURE_SECONDS = 15

IS_WINDOWS = sys.platform == "win32"
INSTALL_WATCH_SECONDS = 30 * 60   # how long the screen watches for an install to finish

PRIVACY_NOTE_DICTATION_ONLY = ("Everything stays on this computer: nothing you say is sent "
                               "anywhere.")
PRIVACY_NOTE = ("Normal dictation never leaves this computer. Requests that start with "
                "\"{word}\" are sent to the assistant's online AI service (Anthropic for "
                "Claude Code, OpenCode's model provider for OpenCode).")


# Dark theme colors
BG = "#1e1f22"
FG = "#e6e6e6"
MUTED = "#a3a3a3"
WARN = "#f5b041"
BUTTON = "#34363b"
BUTTON_ACTIVE = "#43464c"
BORDER = "#4a4d53"
DISABLED = "#6c6f75"
ACCENT = "#5b9cf5"


# Text sizes come from the desktop's own settings (see look.py) and are given to Tk in pixels.
# Spacing is measured in multiples of the body text size ("em"), so it grows and shrinks with it.
WRAP_EM, MIN_WRAP_EM, MAX_WRAP_EM = 35, 24, 60    # how wide text lines are
PAD_EM = 1.2                                      # the window's inner margin
FONT_CHOICES = ("Noto Sans", "Ubuntu", "Cantarell", "DejaVu Sans", "Liberation Sans",
                "Segoe UI", "nimbus sans l", "helvetica")


def pick_font_family(root):
    available = {f.lower(): f for f in tkfont.families(root)}
    for name in FONT_CHOICES:
        if name.lower() in available:
            return available[name.lower()]
    return "TkDefaultFont"


def desktop_look(root):
    """(font family, body text size in pixels, pixels per point) as the desktop shows text."""
    if IS_WINDOWS:
        # Tk starts with Windows' interface font; the process is DPI-aware (see main()).
        px_per_pt = root.winfo_fpixels("1i") / 72
        f = tkfont.nametofont("TkDefaultFont", root).actual()
        size = f.get("size") or 0
        pt = size if size > 0 else (-size / px_per_pt if size else None)
        family, factor = f.get("family"), 1.0
    else:
        px_per_pt = (look.xft_dpi() or 96) / 72
        # Tk otherwise converts sizes with the monitor's physical DPI, which is often far from
        # the desktop's (a wide monitor can report 54 DPI): its smooth-font drawing then makes
        # text up to twice as big as asked. Use the DPI the desktop uses for text.
        root.tk.call("tk", "scaling", px_per_pt)
        family, pt, factor = look.linux_desktop_font()
    available = {name.lower(): name for name in tkfont.families(root)}
    family = available.get((family or "").lower()) or pick_font_family(root)
    return family, round(look.text_points(pt, factor) * px_per_pt), px_per_pt


def set_text_size(root, family, base_px):
    """Use this font and body size (pixels) everywhere: Tk's own fonts (also used by its Yes/No
    dialogs) and the setup window's heading and title fonts."""
    body, head, title = look.sizes(base_px)
    for named in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont", "TkCaptionFont",
                  "TkTooltipFont", "TkIconFont", "TkSmallCaptionFont"):
        try:
            tkfont.nametofont(named, root).configure(family=family, size=body)
        except tk.TclError:
            pass
    # Our named fonts are kept on the window: Tk deletes a named font when its Python object goes
    # away, and the styles using it would silently fall back to a small default.
    own = root.__dict__.setdefault("_ft_fonts", {})
    for name, size in (("FTHeadFont", head), ("FTTitleFont", title)):
        if name in own:
            own[name].configure(family=family, size=size, weight="bold")
        else:
            own[name] = tkfont.Font(root, name=name, family=family, size=size, weight="bold")
    pad = round(-body * 0.8), round(-body * 0.33)
    ttk.Style(root).configure("TButton", padding=pad)


def apply_dark_theme(root, family, base_px):
    """Dark look for the window and for the Tk dialogs it opens (Yes/No questions)."""
    set_text_size(root, family, base_px)
    root.configure(bg=BG)
    for pattern, value in (("*Background", BG), ("*Foreground", FG),
                           ("*activeBackground", BUTTON_ACTIVE), ("*activeForeground", FG),
                           ("*selectBackground", ACCENT), ("*selectForeground", FG),
                           ("*highlightBackground", BG), ("*highlightColor", ACCENT),
                           ("*Button.Background", BUTTON), ("*insertBackground", FG),
                           ("*troughColor", BUTTON), ("*disabledForeground", DISABLED)):
        root.option_add(pattern, value)
    style = ttk.Style(root)
    if "clam" in style.theme_names():
        style.theme_use("clam")
    style.configure(".", background=BG, foreground=FG, fieldbackground=BUTTON,
                    bordercolor=BORDER, lightcolor=BG, darkcolor=BG, focuscolor=ACCENT,
                    troughcolor=BUTTON, font="TkDefaultFont")
    style.configure("TFrame", background=BG)
    style.configure("TLabel", background=BG, foreground=FG)
    style.configure("Title.TLabel", font="FTTitleFont")
    style.configure("Head.TLabel", font="FTHeadFont")
    style.configure("Note.TLabel", foreground=MUTED)
    style.configure("Warn.TLabel", foreground=WARN)
    style.configure("TButton", background=BUTTON, foreground=FG, bordercolor=BORDER,
                    lightcolor=BUTTON, darkcolor=BUTTON)
    style.map("TButton",
              background=[("disabled", BG), ("pressed", BUTTON_ACTIVE), ("active", BUTTON_ACTIVE)],
              foreground=[("disabled", DISABLED)],
              bordercolor=[("disabled", "#33353a"), ("focus", ACCENT)],
              lightcolor=[("pressed", BUTTON_ACTIVE)], darkcolor=[("pressed", BUTTON_ACTIVE)])
    style.configure("Vertical.TScrollbar", background=BUTTON, troughcolor=BG, bordercolor=BG,
                    arrowcolor=FG, lightcolor=BUTTON, darkcolor=BUTTON)
    style.map("Vertical.TScrollbar", background=[("active", BUTTON_ACTIVE)])
    style.configure("TRadiobutton", background=BG, foreground=FG, indicatorbackground=BUTTON,
                    indicatorforeground=FG, indicatormargin=(0, 0, 8, 0))
    style.map("TRadiobutton",
              background=[("active", BG)],
              indicatorbackground=[("selected", ACCENT), ("active", BUTTON_ACTIVE)],
              foreground=[("disabled", DISABLED)])


# Room for the window's title bar and borders, which the desktop adds around the window.
DECOR_W, DECOR_H = 16, 48
MIN_W, MIN_H = 560, 240


def fit_window(need_w, need_h, area, decor=(DECOR_W, DECOR_H), min_size=(MIN_W, MIN_H)):
    """(width, height, x, y) for the window: its natural size, shrunk to fit `area` (the usable
    part of the monitor: without taskbar or panels) and centered in it. The content scrolls
    when it doesn't fit, and Save/Cancel stay visible at the bottom."""
    ax, ay, aw, ah = area
    dw, dh = decor
    w = max(min(need_w, aw - dw), min(min_size[0], aw - dw))
    h = max(min(need_h, ah - dh), min(min_size[1], ah - dh))
    x = ax + max(0, (aw - w - dw) // 2)
    y = ay + max(0, (ah - h - dh) // 2)
    return w, h, x, y


def installed_dir():
    """The install folder if this copy was installed by the installer, else None (dev build)."""
    d = config.data_dir()
    return d if (d / "install.json").exists() and (d / "install.py").exists() else None


class SetupWindow:
    def __init__(self, root, settings, first_run):
        self.root = root
        self.original = config.Settings(settings.harness, dict(settings.trigger), settings.keyword)
        self.trigger = dict(settings.trigger)
        self.first_run = first_run
        self.capture_q = queue.Queue()
        self.capturing = False
        self.installing = {}           # assistant key -> when to stop watching for it

        root.withdraw()                 # shown once it's sized to fit the screen
        root.title("FT Assistant setup")
        self.family, self.base_px, px_per_pt = desktop_look(root)
        self.floor_px = look.shrink_floor(self.base_px, px_per_pt)
        self.dpi_unit = px_per_pt * 72 / 96       # 1.0 at 100 % display scaling
        self.wrapping = []                        # labels whose lines wrap to the window width
        self.wrap = round(WRAP_EM * self.base_px)
        apply_dark_theme(root, self.family, self.base_px)

        # The settings scroll when the window can't be tall enough for them (small screens,
        # large display scaling); Save/Cancel sit below, outside the scrolling part.
        self.canvas = tk.Canvas(root, bg=BG, highlightthickness=0, bd=0)
        self.scrollbar = ttk.Scrollbar(root, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.scrollbar.grid(row=0, column=1, sticky="ns")
        root.rowconfigure(0, weight=1)
        root.columnconfigure(0, weight=1)
        self.pad = round(PAD_EM * self.base_px)
        f = self.content = ttk.Frame(self.canvas, padding=(self.pad, self.pad, self.pad, 4))
        self._content_id = self.canvas.create_window(0, 0, window=f, anchor="nw")
        f.bind("<Configure>", lambda e: self._content_changed())
        self.canvas.bind("<Configure>", self._canvas_resized)
        for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            root.bind_all(seq, self._wheel, add="+")
        self.fitted_need = None
        f.columnconfigure(0, weight=1)
        r = 0
        ttk.Label(f, text="FT Assistant setup", style="Title.TLabel").grid(row=r, sticky="w")
        r += 1
        self.hint = self._wrapping(ttk.Label(f))
        self.hint.grid(row=r, sticky="w", pady=(4, 12))
        r += 1

        # ---- assistant choice
        ttk.Label(f, text="Assistant", style="Head.TLabel").grid(row=r, sticky="w")
        r += 1
        initial = settings.harness
        if first_run and not any(harness.find_exe(h) for h in harness.HARNESSES.values()):
            initial = config.DICTATION_ONLY   # nothing to send requests to yet: suggest typing only
        self.harness_var = tk.StringVar(value=initial)
        self.status = {}
        self.install_btn = {}
        ttk.Radiobutton(f, text="Dictation only: just typing, no assistant",
                        value=config.DICTATION_ONLY, variable=self.harness_var,
                        command=self._refresh).grid(row=r, sticky="w", pady=2)
        r += 1
        for key, label in (("opencode", "OpenCode: free"),
                           ("claude", "Claude Code: needs a Claude subscription")):
            row = ttk.Frame(f)
            row.grid(row=r, sticky="we", pady=2)
            row.columnconfigure(1, weight=1)
            ttk.Radiobutton(row, text=label, value=key, variable=self.harness_var,
                            command=self._refresh).grid(row=0, column=0, sticky="w")
            self.status[key] = ttk.Label(row, style="Note.TLabel")
            self.status[key].grid(row=0, column=1, sticky="e", padx=8)
            self.install_btn[key] = ttk.Button(row, text="Install...",
                                               command=lambda k=key: self._install(k))
            self.install_btn[key].grid(row=0, column=2)
            r += 1
        self.privacy = self._wrapping(ttk.Label(f, text=PRIVACY_NOTE.format(word=settings.keyword),
                                                style="Note.TLabel"))
        self.privacy.grid(row=r, sticky="w", pady=(4, 14))
        r += 1

        # ---- Assistant key
        ttk.Label(f, text="Assistant key", style="Head.TLabel").grid(row=r, sticky="w")
        r += 1
        krow = ttk.Frame(f)
        krow.grid(row=r, sticky="we")
        krow.columnconfigure(0, weight=1)
        self.key_label = ttk.Label(krow)
        self.key_label.grid(row=0, column=0, sticky="w")
        self.change_btn = ttk.Button(krow, text="Change key", command=self._start_capture)
        self.change_btn.grid(row=0, column=1)
        r += 1
        self.capture_msg = self._wrapping(ttk.Label(f, style="Warn.TLabel"))
        self.capture_msg.grid(row=r, sticky="w", pady=(2, 2))
        r += 1
        self._wrapping(ttk.Label(f, text="Good choices: " + keys.GOOD_CHOICES,
                                 style="Note.TLabel")).grid(row=r, sticky="w", pady=(2, 2))
        r += 1
        self._wrapping(ttk.Label(f, text="Best avoided: " + keys.BEST_AVOIDED,
                                 style="Note.TLabel")).grid(row=r, sticky="w", pady=(2, 14))
        r += 1

        # ---- command word
        ttk.Label(f, text="Command word", style="Head.TLabel").grid(row=r, sticky="w")
        r += 1
        wrow = ttk.Frame(f)
        wrow.grid(row=r, sticky="we")
        self.word_var = tk.StringVar(value=settings.keyword)
        tk.Entry(wrow, textvariable=self.word_var, width=22, bg=BUTTON, fg=FG,
                 insertbackground=FG, relief="flat", highlightthickness=1,
                 highlightbackground=BORDER, highlightcolor=ACCENT,
                 font="TkTextFont").grid(row=0, column=0, sticky="w", ipady=3)
        r += 1
        self.word_msg = self._wrapping(ttk.Label(f, style="Note.TLabel"))
        self.word_msg.grid(row=r, sticky="w", pady=(4, 14))
        r += 1
        self.word_var.trace_add("write", lambda *a: self._refresh())

        # ---- updates / uninstall
        ttk.Label(f, text="Updates and uninstall", style="Head.TLabel").grid(row=r, sticky="w")
        r += 1
        urow = ttk.Frame(f)
        urow.grid(row=r, sticky="w", pady=(2, 2))
        self.check_btn = ttk.Button(urow, text="Check for updates", command=self._check_updates)
        self.check_btn.grid(row=0, column=0)
        self.uninstall_btn = ttk.Button(urow, text="Uninstall...", command=self._uninstall,
                                        state="normal" if installed_dir() else "disabled")
        self.uninstall_btn.grid(row=0, column=1, padx=8)
        if buildinfo.is_test_build():
            # A test build from a branch: on its own line, so it stands out and fits.
            r += 1
            self._wrapping(ttk.Label(f, text=f"Version {buildinfo.describe()}",
                                     style="Warn.TLabel")).grid(row=r, sticky="w", pady=(4, 0))
        else:
            ttk.Label(urow, text=f"Version {__version__}", style="Note.TLabel").grid(row=0, column=2)
        r += 1
        self.update_msg = self._wrapping(ttk.Label(f, style="Note.TLabel"))
        self.update_msg.grid(row=r, sticky="w", pady=(4, 2))
        r += 1
        self.update_row = ttk.Frame(f)
        self.update_row.grid(row=r, sticky="w", pady=(2, 14))
        ttk.Button(self.update_row, text="Update now", command=self._update_now).grid(
            row=0, column=0)
        ttk.Button(self.update_row, text="Not now", command=self._not_now).grid(
            row=0, column=1, padx=8)
        self.update_row.grid_remove()
        self.update_q = queue.Queue()
        self.release = None
        r += 1

        # ---- save / cancel (always visible)
        bar = self.bar = ttk.Frame(root, padding=(self.pad, 10, self.pad, 14))
        bar.grid(row=1, column=0, columnspan=2, sticky="we")
        bar.columnconfigure(0, weight=1)
        brow = ttk.Frame(bar)
        brow.grid(row=0, column=0, sticky="e")
        ttk.Button(brow, text="Cancel", command=self._cancel).grid(row=0, column=0, padx=8)
        self.save_btn = ttk.Button(brow, text="Save", command=self._save)
        self.save_btn.grid(row=0, column=1)

        rel = updater.known_update()
        if rel:
            self._show_update(rel)
        root.protocol("WM_DELETE_WINDOW", self._cancel)
        root.bind("<FocusIn>", lambda e: self._refresh())   # e.g. after installing
        self._refresh()
        root.update_idletasks()
        self._fit()
        root.deiconify()

    # ---- size and scrolling

    def _wrapping(self, label):
        """A label whose lines wrap to the window's width (re-wrapped when it's resized)."""
        label.configure(wraplength=self.wrap)
        self.wrapping.append(label)
        return label

    def _set_wrap(self, wrap):
        lo, hi = round(MIN_WRAP_EM * self.base_px), round(MAX_WRAP_EM * self.base_px)
        wrap = max(lo, min(hi, wrap))
        if abs(wrap - self.wrap) > 2:
            self.wrap = wrap
            for label in self.wrapping:
                label.configure(wraplength=wrap)

    def _canvas_resized(self, event):
        """The window was resized (by the user, or to fit the screen): text re-wraps to use the
        new width, and the scrollbar appears or goes as needed."""
        self.canvas.itemconfigure(self._content_id, width=event.width)
        if self.fitted_need is not None:      # not before the window has its real size
            self._set_wrap(event.width - 2 * self.pad)
        self._update_scrollbar()

    def _decor(self):
        """Room for the title bar and borders the desktop adds (they grow with display scaling)."""
        return round(DECOR_W * self.dpi_unit), round(DECOR_H * self.dpi_unit)

    def _min_size(self):
        return (round(MIN_WRAP_EM * self.base_px) + 2 * self.pad + self.scrollbar.winfo_reqwidth(),
                round(MIN_H * self.dpi_unit))

    def _shrink_to_fit(self, area):
        """Before the window is shown, if it's taller than the screen allows: first make it wider
        (longer lines need fewer of them), then make the text a little smaller (down to
        look.FIT_SHRINK of its size, never below 9 points). Whatever still doesn't fit scrolls."""
        dw, dh = self._decor()

        def widen():
            room_w = area[2] - dw - 2 * self.pad - self.scrollbar.winfo_reqwidth()
            self._set_wrap(min(room_w, round(MAX_WRAP_EM * self.base_px)))
            self.root.update_idletasks()

        if self._needed_size()[1] <= area[3] - dh:
            return
        widen()
        while self._needed_size()[1] > area[3] - dh and self.base_px - 1 >= self.floor_px:
            self.base_px -= 1
            set_text_size(self.root, self.family, self.base_px)
            self.pad = round(PAD_EM * self.base_px)
            self.content.configure(padding=(self.pad, self.pad, self.pad, 4))
            self.bar.configure(padding=(self.pad, 10, self.pad, 14))
            widen()

    def _needed_size(self):
        return (self.content.winfo_reqwidth() + self.scrollbar.winfo_reqwidth(),
                self.content.winfo_reqheight() + self.bar.winfo_reqheight())

    def _work_area(self):
        """The usable part of the monitor the mouse is on (without taskbar/panels)."""
        root = self.root
        try:
            area = plat.work_area(*root.winfo_pointerxy())
        except Exception:
            area = None
        if not area or area[2] < 200 or area[3] < 200:
            # Unknown: the whole screen, leaving room for a taskbar
            area = (0, 0, root.winfo_screenwidth(), root.winfo_screenheight() - 80)
        return area

    def _fit(self):
        area = self._work_area()
        if self.fitted_need is None:
            self._shrink_to_fit(area)
        need_w, need_h = self._needed_size()
        decor, min_size = self._decor(), self._min_size()
        w, h, x, y = fit_window(need_w, need_h, area, decor, min_size)
        self.root.minsize(min(min_size[0], w), min(min_size[1], h))
        self.root.maxsize(area[2] - decor[0], area[3] - decor[1])
        self.root.geometry(f"{w}x{h}+{x}+{y}")
        self.fitted_need = need_h

    def _content_changed(self):
        self.canvas.configure(scrollregion=(0, 0, self.content.winfo_reqwidth(),
                                            self.content.winfo_reqheight()))
        self._update_scrollbar()
        # Content grew (an update was found, a warning appeared): grow the window to show it,
        # still within the screen. It never shrinks on its own.
        if self.fitted_need is not None:
            need_h = self._needed_size()[1]
            if need_h > self.fitted_need and self.root.winfo_height() < need_h:
                self._fit()

    def _scrolls(self):
        return self.content.winfo_reqheight() > self.canvas.winfo_height() + 1

    def _update_scrollbar(self):
        if self._scrolls():
            self.scrollbar.grid()
        else:
            self.scrollbar.grid_remove()
            self.canvas.yview_moveto(0)

    def _wheel(self, event):
        if not self._scrolls():
            return
        if getattr(event, "num", None) == 4:
            step = -1
        elif getattr(event, "num", None) == 5:
            step = 1
        else:
            step = -1 if event.delta > 0 else 1
        self.canvas.yview_scroll(step * 3, "units")

    # ---- state

    def _refresh(self):
        name = keys.display_name(self.trigger)
        word, error, warning = textproc.check_keyword(self.word_var.get())
        shown = word or self.original.keyword
        self.hint.configure(text=f"To open this screen again, hold {name} and say "
                                 f"\"{shown} setup\".")
        if error:
            self.word_msg.configure(text=error, style="Warn.TLabel")
        elif warning:
            self.word_msg.configure(text=warning + " It's allowed, but a rarer word works better.",
                                    style="Warn.TLabel")
        else:
            self.word_msg.configure(
                text=f"Start a dictation with \"{word}\" to send it to your assistant, or say "
                     f"\"{word} setup\" to open this screen. After saving, try it a few times: "
                     "some words are easier for the speech engine to catch than others.",
                style="Note.TLabel")
        self.key_label.configure(text=f"Current Assistant key: {name}")
        for key, h in harness.HARNESSES.items():
            installed = harness.find_exe(h) is not None
            if installed:
                self.installing.pop(key, None)
            self.status[key].configure(text="Installed" if installed else
                                       "Installing..." if key in self.installing else
                                       "Not installed")
            if installed or key in self.installing:
                self.install_btn[key].grid_remove()
            else:
                self.install_btn[key].grid()
        choice = self.harness_var.get()
        self.privacy.configure(text=PRIVACY_NOTE_DICTATION_ONLY if choice == config.DICTATION_ONLY
                               else PRIVACY_NOTE.format(word=shown))
        chosen = choice in config.CHOICES
        self.save_btn.configure(state="normal" if chosen and not self.capturing else "disabled")

    # ---- installing a harness

    def _install(self, key):
        h = harness.HARNESSES[key]
        source, _ = harness.install_plan(key)
        if not messagebox.askyesno(
                "Install " + h.name,
                f"This opens a window that downloads and installs the latest {h.name} "
                f"({harness.INSTALL_SIZES[key]}) from {source}\n\nThis screen notices by itself "
                "when it's done.\n\nContinue?", parent=self.root):
            return
        word = textproc.check_keyword(self.word_var.get())[0] or self.original.keyword
        argv = harness.install_window_command(key, word)
        try:
            if IS_WINDOWS:
                subprocess.Popen(argv, env=harness.clean_env(), creationflags=0x10)  # new console
            else:
                subprocess.Popen(argv, env=harness.clean_env(), start_new_session=True,
                                 stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL)
        except OSError as e:
            messagebox.showerror("Install " + h.name, f"Couldn't open the install window ({e}).",
                                 parent=self.root)
            return
        self.installing[key] = time.time() + INSTALL_WATCH_SECONDS
        self._refresh()
        self.root.after(2000, self._watch_installs)

    def _watch_installs(self):
        """Every 2 seconds while an install window may still be working: once the assistant
        turns up, show it as installed and pick it if nothing is chosen yet."""
        for key in list(self.installing):
            if harness.find_exe(harness.HARNESSES[key]):
                self.installing.pop(key)
                if self.harness_var.get() not in config.CHOICES:
                    self.harness_var.set(key)
            elif time.time() > self.installing[key]:
                self.installing.pop(key)          # gave up waiting: offer the button again
        self._refresh()
        if self.installing:
            self.root.after(2000, self._watch_installs)

    # ---- capturing a new Assistant key

    def _start_capture(self):
        self.capturing = True
        self.change_btn.configure(state="disabled")
        self.capture_deadline = time.time() + CAPTURE_SECONDS
        self._show_countdown()
        self._refresh()
        threading.Thread(target=lambda: self.capture_q.put(plat.capture_next(CAPTURE_SECONDS)),
                         daemon=True).start()
        self.root.after(100, self._poll_capture)

    def _show_countdown(self):
        left = max(0, int(round(self.capture_deadline - time.time())))
        self.capture_msg.configure(text=f"Press the key or mouse button you want to use now... "
                                        f"({left} seconds left)")

    def _poll_capture(self):
        try:
            trig = self.capture_q.get_nowait()
        except queue.Empty:
            self._show_countdown()
            self.root.after(100, self._poll_capture)
            return
        self.capturing = False
        self.change_btn.configure(state="normal")
        if trig is None:
            self.capture_msg.configure(text="No key was pressed. The Assistant key is unchanged.")
        elif keys.refusal(trig):
            self.capture_msg.configure(text=keys.refusal(trig) + " The Assistant key is unchanged.")
        elif keys.warning(trig) and not messagebox.askyesno(
                "Use this key?", keys.warning(trig) + "\n\nUse it anyway?", parent=self.root):
            self.capture_msg.configure(text="The Assistant key is unchanged.")
        else:
            self.trigger = trig
            self.capture_msg.configure(text=f"New Assistant key: {keys.display_name(trig)}. "
                                            "Click Save to use it.")
        self._refresh()

    # ---- updates

    def _check_updates(self):
        self.check_btn.configure(state="disabled")
        self.update_msg.configure(text="Checking...", style="Note.TLabel")
        threading.Thread(target=lambda: self.update_q.put(updater.check_now()), daemon=True).start()
        self.root.after(150, self._poll_update)

    def _poll_update(self):
        try:
            status, rel = self.update_q.get_nowait()
        except queue.Empty:
            self.root.after(150, self._poll_update)
            return
        self.check_btn.configure(state="normal")
        if status == "update":
            self._show_update(rel)
        elif status == "latest":
            self.update_row.grid_remove()
            self.update_msg.configure(text=f"You have the latest version ({__version__}).",
                                      style="Note.TLabel")
        else:
            self.update_msg.configure(text="Couldn't reach GitHub. Check your internet "
                                           "connection and try again later.", style="Warn.TLabel")

    def _show_update(self, rel):
        self.release = rel
        notes = "\n".join(rel.notes.splitlines()[:8]) or "(no release notes)"
        self.update_msg.configure(text=f"Version {rel.version} is available.\n\nWhat's new:\n"
                                       f"{notes}", style="Warn.TLabel")
        self.update_row.grid()

    def _update_now(self):
        d = installed_dir()
        if not d:
            # Development build (not installed): just show the release.
            if self.release and self.release.url:
                webbrowser.open(self.release.url)
            self.update_msg.configure(text="This copy isn't installed, so it can't update itself. "
                                           "The release page is open in your browser.",
                                      style="Note.TLabel")
            self.update_row.grid_remove()
            return
        if not messagebox.askyesno(
                "Update FT Assistant",
                f"Download and install version {self.release.version} now? FT Assistant restarts "
                "when it's done, and the current version is kept so it can be rolled back.",
                parent=self.root):
            return
        self._run_installer(d, ["update", "--dir", str(d)])
        self.root.destroy()
        sys.exit(0)

    def _uninstall(self):
        d = installed_dir()
        if not d or not messagebox.askyesno(
                "Uninstall FT Assistant",
                "This opens a window that removes FT Assistant: the program, its Python, the speech "
                "engine, GPU libraries, the Whisper model, and its menu and login entries. "
                "Claude Code and OpenCode stay installed.\n\nContinue?", parent=self.root):
            return
        self._run_installer(d, ["uninstall", "--dir", str(d)])
        self.root.destroy()
        sys.exit(0)

    def _run_installer(self, d, args):
        """Run the installed installer in a visible terminal window."""
        if IS_WINDOWS:
            venv = d / "python" / "Scripts" / "python.exe"
            py = venv if venv.exists() else d / "python" / "python.exe"
            subprocess.Popen([str(py), str(d / "install.py")] + args + ["--pause"],
                             env=harness.clean_env(), creationflags=0x10)   # new console
            return
        py = d / "python" / "bin" / "python3"
        script = (" ".join(f"'{x}'" for x in [str(py), str(d / "install.py")] + args)
                  + "; echo; read -p 'Press Enter to close this window. '")
        argv = harness.terminal_command(["bash", "-c", script], str(d))
        subprocess.Popen(argv, env=harness.clean_env(), start_new_session=True,
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)

    def _not_now(self):
        if self.release:
            state = updater.load_state()
            updater.mark_not_now(state, self.release.version)
            updater.save_state(state)
        self.update_row.grid_remove()
        self.update_msg.configure(text="OK. You'll get one more reminder in a few days.",
                                  style="Note.TLabel")

    # ---- closing

    def _save(self):
        word, error, warning = textproc.check_keyword(self.word_var.get())
        if error:
            messagebox.showwarning("Command word", error, parent=self.root)
            return
        if warning and word != self.original.keyword and not messagebox.askyesno(
                "Use this command word?", warning + "\n\nUse it anyway?", parent=self.root):
            return
        new = config.Settings(self.harness_var.get(), dict(self.trigger), word)
        if new.harness not in config.CHOICES:
            return
        # Dictation only needs no assistant, so there's nothing to check or ask about.
        if new.uses_assistant and not harness.find_exe(harness.HARNESSES[new.harness]) \
                and not messagebox.askyesno(
                "Not installed",
                f"{harness.HARNESSES[new.harness].name} isn't installed yet, so \"Assistant\" "
                "requests won't work until it is. Save anyway?", parent=self.root):
            return
        config.save(new)
        self.root.destroy()
        sys.exit(CHANGED if new != self.original else 0)

    def _cancel(self):
        if self.first_run and not messagebox.askyesno(
                "Close setup?", "Nothing is chosen yet, so \"Assistant\" requests won't work. "
                "Normal dictation still works. Close anyway?", parent=self.root):
            return
        self.root.destroy()
        sys.exit(0)


def dpi_aware():
    """Windows: draw at the screen's real resolution, so text stays sharp with display scaling
    (otherwise Windows stretches the whole window, blurring it). Tk then sizes text in points
    by the real DPI."""
    if not IS_WINDOWS:
        return
    import ctypes
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)      # system DPI aware (Windows 8.1+)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()       # Windows Vista+
        except Exception:
            pass


def main():
    settings = config.load()
    dpi_aware()
    root = tk.Tk()
    SetupWindow(root, settings, first_run=not settings.harness_chosen)
    root.mainloop()


if __name__ == "__main__":
    main()
