"""Text size and font for the setup window, taken from the desktop's own settings.

The setup window used to draw every text in a fixed size (15 pixels). That's too big on a
desktop set to 10-point text, and could be too small on a high-resolution screen. Now it uses the
same font and size as the rest of the user's desktop, so it reads like any other window there:

- Linux: the desktop's interface font ("Ubuntu 10" in Cinnamon's or GNOME's settings, MATE,
  Xfce or KDE), times its "text scaling" factor, converted to pixels at the desktop's font DPI
  (Xft.dpi). Pixels, because Tk would otherwise use the X server's physical DPI, which is often
  wrong (a wide monitor can report 54 DPI and make 10-point text tiny).
- Windows: Windows' own interface font and size, which is what Tk starts with; the window is
  made DPI-aware, so the size follows Windows' display scaling and stays sharp.

The size is kept readable: never below 9 points or above 18 points (accessibility settings up
to that are honoured). If the window still doesn't fit the screen, setup_ui shrinks the text a
little (at most to 85 %, never below 9 points) before the content scrolls."""

import os
import re
import subprocess

DEFAULT_PT = 10.0
MIN_PT, MAX_PT = 9.0, 18.0
FIT_SHRINK = 0.85          # how far the text may shrink to fit the screen before it scrolls
HEAD_RATIO, TITLE_RATIO = 1.15, 1.45
_STYLE_WORDS = {"regular", "book", "normal", "medium", "bold", "semi-bold", "semibold",
                "demi-bold", "demibold", "extra-bold", "light", "semi-light", "extra-light",
                "thin", "heavy", "black", "italic", "oblique", "condensed", "semi-condensed"}


def parse_font_name(text):
    """("family", points) from a desktop font setting, or (None, None).
    Pango/GTK: "Ubuntu 10", "Noto Sans Bold 11", "'Cantarell 11'" (gsettings quotes it).
    KDE: "Noto Sans,10,-1,5,50,0,0,0,0,0"."""
    s = (text or "").strip().strip("'\"").strip()
    if not s:
        return None, None
    if "," in s:                                   # KDE
        parts = [p.strip() for p in s.split(",")]
        try:
            size = float(parts[1])
        except (IndexError, ValueError):
            size = None
        return (parts[0] or None), (size if size and size > 0 else None)
    m = re.match(r"^(.*?)[\s,]+(\d+(?:\.\d+)?)$", s)
    family, size = (m.group(1), float(m.group(2))) if m else (s, None)
    words = family.split()
    while len(words) > 1 and words[-1].lower() in _STYLE_WORDS:
        words.pop()
    return (" ".join(words) or None), size


def _run(cmd):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
    except (OSError, subprocess.SubprocessError):
        return None
    out = r.stdout.strip()
    return out if r.returncode == 0 and out else None


def _float(text):
    try:
        return float((text or "").strip().strip("'\""))
    except ValueError:
        return None


def linux_desktop_font(run=_run, env=None):
    """(family or None, points or None, text scaling factor) from the desktop's settings."""
    env = os.environ if env is None else env
    desk = env.get("XDG_CURRENT_DESKTOP", "").lower()

    def gsettings(schema, scaling=True):
        fam, pt = parse_font_name(run(["gsettings", "get", schema, "font-name"]))
        if not pt:
            return None
        factor = _float(run(["gsettings", "get", schema, "text-scaling-factor"])) if scaling else None
        return fam, pt, factor or 1.0

    def xfce():
        fam, pt = parse_font_name(run(["xfconf-query", "-c", "xsettings", "-p", "/Gtk/FontName"]))
        return (fam, pt, 1.0) if pt else None

    def kde():
        for tool in ("kreadconfig6", "kreadconfig5"):
            fam, pt = parse_font_name(run([tool, "--file", "kdeglobals", "--group", "General",
                                           "--key", "font"]))
            if pt:
                return fam, pt, 1.0
        return None

    sources = {
        "cinnamon": lambda: gsettings("org.cinnamon.desktop.interface"),
        "gnome": lambda: gsettings("org.gnome.desktop.interface"),
        "mate": lambda: gsettings("org.mate.interface", scaling=False),
        "xfce": xfce,
        "kde": kde,
    }
    first = [k for k in ("cinnamon", "mate", "xfce", "kde") if k in desk]
    if any(k in desk for k in ("gnome", "unity", "budgie", "pantheon", "ubuntu")):
        first.append("gnome")
    order = first + [k for k in ("cinnamon", "gnome", "mate", "xfce", "kde") if k not in first]
    for key in order:
        found = sources[key]()
        if found:
            return found
    return None, None, 1.0


def xft_dpi(run=_run):
    """The DPI the desktop uses for text (the Xft.dpi setting), or None."""
    for line in (run(["xrdb", "-query"]) or "").splitlines():
        if line.startswith("Xft.dpi:"):
            dpi = _float(line.split(":", 1)[1])
            if dpi and 48 <= dpi <= 480:
                return dpi
    return None


def text_points(points, factor=1.0):
    """The interface text size in points: the desktop's, kept between MIN_PT and MAX_PT."""
    pt = (points or DEFAULT_PT) * (factor or 1.0)
    return max(MIN_PT, min(MAX_PT, pt))


def sizes(base_px):
    """Pixel sizes (negative, as Tk wants pixels) for body text, headings and the title."""
    base = max(1, round(base_px))
    return -base, -round(base * HEAD_RATIO), -round(base * TITLE_RATIO)


def shrink_floor(base_px, px_per_pt):
    """The smallest body size (pixels) the window may shrink to when fitting the screen."""
    return max(MIN_PT * px_per_pt, base_px * FIT_SHRINK)
