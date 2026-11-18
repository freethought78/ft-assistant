"""Names and rules for the Assistant key (pure functions, unit-tested).

A trigger is {"type": "key", "keysym": "<X keysym name>"} or {"type": "button", "button": n}."""

# Mouse buttons that can never be the Assistant key.
REFUSED_BUTTONS = {
    1: "Left click can't be the Assistant key: you need it for everything else.",
    2: "Middle click can't be the Assistant key: it's used for pasting and scrolling.",
    3: "Right click can't be the Assistant key: you need it for menus.",
    4: "The scroll wheel can't be the Assistant key.",
    5: "The scroll wheel can't be the Assistant key.",
    6: "Tilting the scroll wheel can't be the Assistant key.",
    7: "Tilting the scroll wheel can't be the Assistant key.",
}

_FRIENDLY = {
    "Caps_Lock": "Caps Lock", "Scroll_Lock": "Scroll Lock", "Num_Lock": "Num Lock",
    "Pause": "Pause", "Insert": "Insert", "Menu": "Menu key", "Print": "Print Screen",
    "Escape": "Esc", "Return": "Enter", "KP_Enter": "keypad Enter", "space": "Space",
    "Tab": "Tab", "BackSpace": "Backspace", "Delete": "Delete", "Home": "Home", "End": "End",
    "Prior": "Page Up", "Next": "Page Down",
    "Left": "Left arrow", "Right": "Right arrow", "Up": "Up arrow", "Down": "Down arrow",
    "Shift_L": "Left Shift", "Shift_R": "Right Shift", "Control_L": "Left Ctrl",
    "Control_R": "Right Ctrl", "Alt_L": "Left Alt", "Alt_R": "Right Alt",
    "ISO_Level3_Shift": "AltGr", "Super_L": "Windows key", "Super_R": "Right Windows key",
    "Meta_L": "Left Meta", "Meta_R": "Right Meta",
}

_TYPING = {"space", "Return", "KP_Enter", "Tab", "BackSpace", "Delete",
           "Left", "Right", "Up", "Down", "Home", "End", "Prior", "Next"}
_SHORTCUT = {"Shift_L", "Shift_R", "Control_L", "Control_R", "Alt_L", "Alt_R",
             "ISO_Level3_Shift", "Super_L", "Super_R", "Meta_L", "Meta_R", "Hyper_L", "Hyper_R"}
_OTHER_APPS = {"Escape", "Print"}

GOOD_CHOICES = ("Caps Lock, Scroll Lock, Pause, Insert, the Menu key, F13-F24 if your keyboard "
                "has them, or a spare side button on your mouse. Pick one you can hold "
                "comfortably while speaking.")
BEST_AVOIDED = ("Letters, numbers, Space, Enter, Tab, Backspace and arrows (you need them to "
                "type); Shift, Ctrl, Alt and the Windows key (used in shortcuts); Esc and Print "
                "Screen (other programs use them).")


def display_name(trigger):
    if trigger.get("type") == "button":
        return f"mouse button {trigger.get('button')}"
    sym = trigger.get("keysym", "")
    if sym in _FRIENDLY:
        return _FRIENDLY[sym]
    if len(sym) == 1:
        return f"the {sym.upper()} key"
    if sym.startswith("KP_"):
        return f"keypad {sym[3:]}"
    return sym.replace("_", " ")


def refusal(trigger):
    """A message if this trigger is never allowed, else None."""
    if trigger.get("type") == "button":
        return REFUSED_BUTTONS.get(trigger.get("button"))
    return None


def warning(trigger):
    """A message if this trigger is allowed but best avoided, else None."""
    if trigger.get("type") != "key":
        return None
    sym = trigger.get("keysym", "")
    name = display_name(trigger)
    if len(sym) == 1 and sym.isalnum() or sym.startswith("KP_") and sym[3:].isdigit() \
            or sym in _TYPING:
        return f"{name} is a key you need for typing. While it's the Assistant key it won't type."
    if sym in _SHORTCUT:
        return f"{name} is used in keyboard shortcuts. Shortcuts with it may stop working."
    if sym in _OTHER_APPS:
        return f"{name} is used by other programs. They won't receive it any more."
    return None
