"""The setup screen ("Assistant setup").

Run as its own process (python -m ft_assistant.setup_ui) so the main app keeps running.
Exit code 10 means settings were saved and changed; 0 means nothing changed."""

import queue
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import font as tkfont
from tkinter import messagebox, ttk

from . import __version__, config, harness, keys, updater
from . import platform_linux as plat

CHANGED = 10
CAPTURE_SECONDS = 15

# Official install commands, run in a visible terminal only after the user agrees.
INSTALL_COMMANDS = {
    "claude": "curl -fsSL https://claude.ai/install.sh | bash",
    "opencode": "curl -fsSL https://opencode.ai/install | bash",
}
INSTALL_SIZES = {"claude": "about 350 MB", "opencode": "about 400 MB"}

PRIVACY_NOTE = ("Normal dictation never leaves this computer. Requests that start with "
                "\"Assistant\" are sent to the assistant's online AI service (Anthropic for "
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


# Font sizes in pixels (negative = pixels), so the text is the same size whether Tk draws with
# the desktop's smooth fonts or, as in the installer's own Python, with the older X11 fonts.
BASE_PX, HEAD_PX, TITLE_PX = -15, -17, -22
FONT_CHOICES = ("Noto Sans", "Ubuntu", "Cantarell", "DejaVu Sans", "Liberation Sans",
                "Segoe UI", "nimbus sans l", "helvetica")


def pick_font_family(root):
    available = {f.lower(): f for f in tkfont.families(root)}
    for name in FONT_CHOICES:
        if name.lower() in available:
            return available[name.lower()]
    return "TkDefaultFont"


def apply_fonts(root):
    family = pick_font_family(root)
    for named in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont", "TkCaptionFont",
                  "TkTooltipFont", "TkIconFont", "TkSmallCaptionFont"):
        try:
            tkfont.nametofont(named, root).configure(family=family, size=BASE_PX)
        except tk.TclError:
            pass
    return family


def apply_dark_theme(root):
    """Dark look for the window and for the Tk dialogs it opens (Yes/No questions)."""
    family = apply_fonts(root)
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
                    troughcolor=BUTTON, font=(family, BASE_PX))
    style.configure("TFrame", background=BG)
    style.configure("TLabel", background=BG, foreground=FG)
    style.configure("Title.TLabel", font=(family, TITLE_PX, "bold"))
    style.configure("Head.TLabel", font=(family, HEAD_PX, "bold"))
    style.configure("Note.TLabel", foreground=MUTED)
    style.configure("Warn.TLabel", foreground=WARN)
    style.configure("TButton", background=BUTTON, foreground=FG, bordercolor=BORDER,
                    lightcolor=BUTTON, darkcolor=BUTTON, padding=(12, 5))
    style.map("TButton",
              background=[("disabled", BG), ("pressed", BUTTON_ACTIVE), ("active", BUTTON_ACTIVE)],
              foreground=[("disabled", DISABLED)],
              bordercolor=[("disabled", "#33353a"), ("focus", ACCENT)],
              lightcolor=[("pressed", BUTTON_ACTIVE)], darkcolor=[("pressed", BUTTON_ACTIVE)])
    style.configure("TRadiobutton", background=BG, foreground=FG, indicatorbackground=BUTTON,
                    indicatorforeground=FG, indicatormargin=(0, 0, 8, 0))
    style.map("TRadiobutton",
              background=[("active", BG)],
              indicatorbackground=[("selected", ACCENT), ("active", BUTTON_ACTIVE)],
              foreground=[("disabled", DISABLED)])


def installed_dir():
    """The install folder if this copy was installed by the installer, else None (dev build)."""
    d = config.data_dir()
    return d if (d / "install.json").exists() and (d / "install.py").exists() else None


class SetupWindow:
    def __init__(self, root, settings, first_run):
        self.root = root
        self.original = config.Settings(settings.harness, dict(settings.trigger))
        self.trigger = dict(settings.trigger)
        self.first_run = first_run
        self.capture_q = queue.Queue()
        self.capturing = False

        root.title("FT Assistant setup")
        root.minsize(560, 0)
        apply_dark_theme(root)

        f = ttk.Frame(root, padding=18)
        f.grid(sticky="nsew")
        root.columnconfigure(0, weight=1)
        f.columnconfigure(0, weight=1)
        r = 0
        ttk.Label(f, text="FT Assistant setup", style="Title.TLabel").grid(row=r, sticky="w")
        r += 1
        self.hint = ttk.Label(f, wraplength=520)
        self.hint.grid(row=r, sticky="w", pady=(4, 12))
        r += 1

        # ---- assistant choice
        ttk.Label(f, text="Assistant", style="Head.TLabel").grid(row=r, sticky="w")
        r += 1
        self.harness_var = tk.StringVar(value=settings.harness)
        self.status = {}
        self.install_btn = {}
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
        ttk.Label(f, text=PRIVACY_NOTE, wraplength=520, style="Note.TLabel").grid(
            row=r, sticky="w", pady=(4, 14))
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
        self.capture_msg = ttk.Label(f, wraplength=520, style="Warn.TLabel")
        self.capture_msg.grid(row=r, sticky="w", pady=(2, 2))
        r += 1
        ttk.Label(f, text="Good choices: " + keys.GOOD_CHOICES, wraplength=520,
                  style="Note.TLabel").grid(row=r, sticky="w", pady=(2, 2))
        r += 1
        ttk.Label(f, text="Best avoided: " + keys.BEST_AVOIDED, wraplength=520,
                  style="Note.TLabel").grid(row=r, sticky="w", pady=(2, 14))
        r += 1

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
        ttk.Label(urow, text=f"Version {__version__}", style="Note.TLabel").grid(row=0, column=2)
        r += 1
        self.update_msg = ttk.Label(f, wraplength=520, style="Note.TLabel")
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

        # ---- save / cancel
        brow = ttk.Frame(f)
        brow.grid(row=r, sticky="e")
        ttk.Button(brow, text="Cancel", command=self._cancel).grid(row=0, column=0, padx=8)
        self.save_btn = ttk.Button(brow, text="Save", command=self._save)
        self.save_btn.grid(row=0, column=1)

        rel = updater.known_update()
        if rel:
            self._show_update(rel)
        root.protocol("WM_DELETE_WINDOW", self._cancel)
        root.bind("<FocusIn>", lambda e: self._refresh())   # e.g. after installing
        self._refresh()

    # ---- state

    def _refresh(self):
        name = keys.display_name(self.trigger)
        self.hint.configure(text=f"To open this screen again, hold {name} and say "
                                 "\"Assistant setup\".")
        self.key_label.configure(text=f"Current Assistant key: {name}")
        for key, h in harness.HARNESSES.items():
            installed = harness.find_exe(h) is not None
            self.status[key].configure(text="Installed" if installed else "Not installed")
            if installed:
                self.install_btn[key].grid_remove()
            else:
                self.install_btn[key].grid()
        chosen = self.harness_var.get() in config.HARNESSES
        self.save_btn.configure(state="normal" if chosen and not self.capturing else "disabled")

    # ---- installing a harness

    def _install(self, key):
        h = harness.HARNESSES[key]
        cmd = INSTALL_COMMANDS[key]
        if not messagebox.askyesno(
                "Install " + h.name,
                f"This opens a terminal window that downloads and installs {h.name} from its "
                f"official website ({INSTALL_SIZES[key]}):\n\n{cmd}\n\nContinue?", parent=self.root):
            return
        if key == "claude":
            after = "echo; echo 'Next: run  claude  once to sign in with your Claude account.'"
        else:
            after = "echo; echo 'Done.'"
        script = f"{cmd}; {after}; echo; read -p 'Press Enter to close this window. '"
        argv = harness.terminal_command(["bash", "-lc", script], str(config.sessions_dir().parent))
        subprocess.Popen(argv, env=harness.clean_env(), start_new_session=True,
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)

    # ---- capturing a new Assistant key

    def _start_capture(self):
        self.capturing = True
        self.change_btn.configure(state="disabled")
        self.capture_msg.configure(text=f"Press the key or mouse button you want to use "
                                        f"(waiting {CAPTURE_SECONDS} seconds)...")
        self._refresh()
        threading.Thread(target=lambda: self.capture_q.put(plat.capture_next(CAPTURE_SECONDS)),
                         daemon=True).start()
        self.root.after(100, self._poll_capture)

    def _poll_capture(self):
        try:
            trig = self.capture_q.get_nowait()
        except queue.Empty:
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
                subprocess.Popen(["xdg-open", self.release.url], stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL, start_new_session=True)
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
        new = config.Settings(self.harness_var.get(), dict(self.trigger))
        if new.harness not in config.HARNESSES:
            return
        if not harness.find_exe(harness.HARNESSES[new.harness]) and not messagebox.askyesno(
                "Not installed",
                f"{harness.HARNESSES[new.harness].name} isn't installed yet, so \"Assistant\" "
                "requests won't work until it is. Save anyway?", parent=self.root):
            return
        config.save(new)
        self.root.destroy()
        sys.exit(CHANGED if new != self.original else 0)

    def _cancel(self):
        if self.first_run and not messagebox.askyesno(
                "Close setup?", "No assistant is chosen yet, so \"Assistant\" requests won't work. "
                "Normal dictation still works. Close anyway?", parent=self.root):
            return
        self.root.destroy()
        sys.exit(0)


def main():
    settings = config.load()
    root = tk.Tk()
    SetupWindow(root, settings, first_run=not settings.harness_chosen)
    root.mainloop()


if __name__ == "__main__":
    main()
