"""The voice commands window: every spoken command, one line each, with the user's own command
word. Opened by the "Voice commands..." button on the setup screen, or by saying "<word> help"
(then as its own process: python -m ft_assistant.voice_commands).

The list stays short on purpose (at most about 7 commands): FT Assistant should stay simple and
easy to understand out of the box. See the voice commands plan in docs/design-notes.md."""

import tkinter as tk
from tkinter import ttk

from . import config, keys

# (what to say, what it does, works without an assistant ("Dictation only"))
COMMANDS = (
    ("{w}, ...", "Sends what you say after it to your assistant as a request.", False),
    ("{w}", "Opens your assistant's window, with the current conversation.", False),
    ("{w} stop", "Stops what your assistant is doing right now, like pressing Esc in its window.",
     False),
    ("{w} setup", "Opens the setup screen.", True),
    ("{w} help", "Shows this list.", True),
)
TITLE = "FT Assistant voice commands"


def command_list(word, dictation_only=False):
    """[(what to say, what it does)] for this command word."""
    return [(say.format(w=word), does) for say, does, always in COMMANDS
            if always or not dictation_only]


def notes(word, dictation_only=False):
    out = [f"Anything you say without \"{word}\" first is typed where your cursor is."]
    if dictation_only:
        out.append("Requests to an assistant work once you choose one on the setup screen.")
    else:
        out.append("When your assistant asks to approve something, answer with the keyboard: "
                   "voice never approves anything.")
    return out


def fill(win, word, key_name, dictation_only, base_px, on_close):
    """Put the list into `win` (a Tk root or Toplevel, already themed)."""
    pad = round(1.2 * base_px)
    wrap = round(26 * base_px)
    f = ttk.Frame(win, padding=(pad, pad, pad, pad))
    f.grid(sticky="nsew")
    f.columnconfigure(1, weight=1)
    ttk.Label(f, text="Voice commands", style="Title.TLabel").grid(row=0, columnspan=2, sticky="w")
    ttk.Label(f, text=f"Hold {key_name} and say:").grid(row=1, columnspan=2, sticky="w",
                                                         pady=(4, 10))
    r = 2
    for say, does in command_list(word, dictation_only):
        ttk.Label(f, text=f"“{say}”", style="Head.TLabel").grid(
            row=r, column=0, sticky="nw", padx=(0, pad), pady=3)
        ttk.Label(f, text=does, wraplength=wrap).grid(row=r, column=1, sticky="nw", pady=3)
        r += 1
    for i, line in enumerate(notes(word, dictation_only)):
        ttk.Label(f, text=line, wraplength=wrap + round(8 * base_px), style="Note.TLabel").grid(
            row=r, columnspan=2, sticky="w", pady=(10 if i == 0 else 4, 0))
        r += 1
    close = ttk.Button(f, text="Close", command=on_close)
    close.grid(row=r, columnspan=2, sticky="e", pady=(pad, 0))
    win.bind("<Escape>", lambda e: on_close())
    win.bind("<Return>", lambda e: on_close())
    close.focus_set()
    return f


def place(win, near=None):
    """Center on `near` (the setup screen) or on the screen's usable area."""
    win.update_idletasks()
    w, h = win.winfo_reqwidth(), win.winfo_reqheight()
    if near is not None:
        x = near.winfo_rootx() + (near.winfo_width() - w) // 2
        y = near.winfo_rooty() + (near.winfo_height() - h) // 3
    else:
        from . import plat
        try:
            ax, ay, aw, ah = plat.work_area(*win.winfo_pointerxy())
        except Exception:
            ax, ay, aw, ah = 0, 0, win.winfo_screenwidth(), win.winfo_screenheight() - 80
        x, y = ax + (aw - w) // 2, ay + (ah - h) // 3
    win.geometry(f"+{max(0, x)}+{max(0, y)}")


def open_from_setup(parent, word, key_name, dictation_only, base_px):
    """The window over the setup screen (shares its look). Returns the Toplevel."""
    top = tk.Toplevel(parent)
    top.withdraw()
    top.title(TITLE)
    top.transient(parent)
    top.configure(bg=parent.cget("bg"))
    fill(top, word, key_name, dictation_only, base_px, top.destroy)
    place(top, parent)
    top.deiconify()
    return top


def main():
    """On its own, for "<word> help": with the saved settings."""
    from . import setup_ui              # its look (fonts, dark theme); imported here, not above
    settings = config.load()
    setup_ui.dpi_aware()
    root = tk.Tk()
    root.withdraw()
    root.title(TITLE)
    family, base_px, _ = setup_ui.desktop_look(root)
    setup_ui.apply_dark_theme(root, family, base_px)
    fill(root, settings.keyword, keys.display_name(settings.trigger), settings.dictation_only,
         base_px, root.destroy)
    place(root)
    root.deiconify()
    root.lift()
    root.attributes("-topmost", True)                 # in front of the window being dictated to,
    root.after(500, lambda: root.attributes("-topmost", False))       # then like any other
    root.focus_force()
    root.mainloop()


if __name__ == "__main__":
    main()
