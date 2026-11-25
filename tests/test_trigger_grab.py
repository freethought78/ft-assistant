"""The Assistant key never reaches other programs, whether it's a keyboard key or any mouse
button (Linux). A mouse button that the window under the cursor also got made Chromium-based apps
come to the front and take the dictation (found 2026-11-25)."""
import os
import unittest
from unittest import mock

try:
    from ft_assistant import platform_linux
    from Xlib import X
except Exception:                      # not Linux / no python-xlib
    platform_linux = None


@unittest.skipIf(platform_linux is None or os.name == "nt", "Linux")
class Grab(unittest.TestCase):
    def grab(self, trigger, error=False):
        lst = platform_linux.TriggerListener(trigger, lambda: None, lambda: None)
        lst.keycode = 66 if trigger["type"] == "key" else None
        d = mock.Mock()
        d.next_event.side_effect = OSError          # ends the drain thread at once
        root = d.screen.return_value.root
        if error:
            root.grab_button.side_effect = lambda *a, onerror: onerror("BadAccess")
            root.grab_key.side_effect = lambda *a, onerror: onerror("BadAccess")
        with self.assertNoLogs("ft_assistant", "WARNING") if not error else \
                self.assertLogs("ft_assistant", "WARNING"):
            lst._grab(lambda: d)
        return root

    def test_any_mouse_button_is_grabbed(self):
        for button in (8, 9, 10, 12, 15):              # whichever the user chose
            root = self.grab({"type": "button", "button": button})
            args = root.grab_button.call_args.args
            self.assertEqual(args[0], button)
            self.assertEqual(args[1], X.AnyModifier)          # with any modifier held
            self.assertFalse(args[2])                          # events go to FT Assistant only
            root.grab_key.assert_not_called()

    def test_keyboard_keys_still_grabbed(self):
        root = self.grab({"type": "key", "keysym": "Caps_Lock"})
        self.assertEqual(root.grab_key.call_args.args[:2], (66, X.AnyModifier))
        root.grab_button.assert_not_called()

    def test_taken_by_another_program_warns_and_still_works(self):
        self.grab({"type": "button", "button": 12}, error=True)


if __name__ == "__main__":
    unittest.main()
