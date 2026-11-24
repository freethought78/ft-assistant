"""Desktop notifications only for problems and updates, never for normal use or for a voice
command that simply did nothing (the user's decision, 2026-11-24: don't flood the screen)."""
import ast
import unittest
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent / "ft_assistant"

# Each notification's opening words. Adding one means adding it here, on purpose.
ALLOWED = {
    "Microphone error",                         # dictation can't work
    "Error: ",                                  # a dictation failed
    "No assistant chosen yet",                  # "Assistant, ..." before choosing one
    "Couldn't open ",                           # the assistant's window didn't open
    "Your graphics card couldn't be used",      # slow: the processor took over
    "FT Assistant ",                            # an update is available
}


def opening(arg):
    """The literal start of a notification's text (an f-string's first constant part)."""
    if isinstance(arg, ast.Constant):
        return arg.value
    if isinstance(arg, ast.JoinedStr) and arg.values and isinstance(arg.values[0], ast.Constant):
        return arg.values[0].value
    return None                       # a variable: the start-up problem from session_problem()


def notifications():
    for f in sorted(PKG.glob("*.py")):
        for node in ast.walk(ast.parse(f.read_text())):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr in ("notify", "notify_with_action")
                    and isinstance(node.func.value, ast.Name) and node.func.value.id == "plat"):
                yield f.name, opening(node.args[0]) if node.args else None


class NotificationPolicy(unittest.TestCase):
    def test_only_problems_and_updates(self):
        for name, text in notifications():
            if text is None:
                continue
            self.assertTrue(any(text.startswith(a) for a in ALLOWED),
                            f"{name}: new notification {text!r}: is it a problem or an update?")

    def test_commands_that_did_nothing_stay_silent(self):
        texts = " ".join(t or "" for _, t in notifications())
        for silent in ("Nothing to undo", "Nothing was undone", "No assistant window is open"):
            self.assertNotIn(silent, texts)


if __name__ == "__main__":
    unittest.main()
