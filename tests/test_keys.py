import unittest

from ft_assistant import keys


def key(sym):
    return {"type": "key", "keysym": sym}


def button(n):
    return {"type": "button", "button": n}


class Keys(unittest.TestCase):
    def test_names(self):
        self.assertEqual(keys.display_name(key("Caps_Lock")), "Caps Lock")
        self.assertEqual(keys.display_name(key("F13")), "F13")
        self.assertEqual(keys.display_name(key("a")), "the A key")
        self.assertEqual(keys.display_name(key("Super_L")), "Windows key")
        self.assertEqual(keys.display_name(button(12)), "mouse button 12")

    def test_refused(self):
        for n in range(1, 8):
            self.assertIsNotNone(keys.refusal(button(n)), n)
        self.assertIsNone(keys.refusal(button(8)))
        self.assertIsNone(keys.refusal(button(12)))
        self.assertIsNone(keys.refusal(key("a")))

    def test_good_keys_have_no_warning(self):
        for sym in ("Caps_Lock", "Scroll_Lock", "Pause", "Insert", "Menu", "F13", "F24"):
            self.assertIsNone(keys.warning(key(sym)), sym)
        self.assertIsNone(keys.warning(button(9)))

    def test_avoided_keys_warn(self):
        for sym in ("a", "Z", "5", "space", "Return", "Tab", "BackSpace", "Left", "KP_5",
                    "Shift_L", "Control_R", "Alt_L", "Super_L", "Escape", "Print"):
            self.assertIsNotNone(keys.warning(key(sym)), sym)


if __name__ == "__main__":
    unittest.main()
