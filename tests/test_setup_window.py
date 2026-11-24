import unittest

try:
    from ft_assistant import setup_ui
except ImportError:          # no Tk in this Python
    setup_ui = None


@unittest.skipIf(setup_ui is None, "needs tkinter")
class FitWindow(unittest.TestCase):
    def test_natural_size_when_it_fits(self):
        w, h, x, y = setup_ui.fit_window(600, 700, (0, 0, 2560, 1400))
        self.assertEqual((w, h), (600, 700))
        self.assertEqual(x, (2560 - 600 - setup_ui.DECOR_W) // 2)

    def test_never_below_the_taskbar(self):
        # 1366x768 laptop, 40 px taskbar at the bottom: usable area is 728 px tall
        area = (0, 0, 1366, 728)
        w, h, x, y = setup_ui.fit_window(600, 900, area)
        self.assertLessEqual(y + h + setup_ui.DECOR_H, 728)
        self.assertGreaterEqual(y, 0)

    def test_scaled_display(self):
        # 1920x1080 at 150% scaling looks like 1280x720 to the program, taskbar 32 px
        w, h, x, y = setup_ui.fit_window(600, 900, (0, 0, 1280, 688))
        self.assertLessEqual(y + h + setup_ui.DECOR_H, 688)
        self.assertLessEqual(x + w + setup_ui.DECOR_W, 1280)

    def test_taskbar_at_top_or_second_monitor(self):
        # Work area that doesn't start at 0,0 (taskbar on top; or the monitor on the right)
        area = (2560, 360, 1920, 1040)
        w, h, x, y = setup_ui.fit_window(600, 1200, area)
        self.assertGreaterEqual(y, 360)
        self.assertLessEqual(y + h + setup_ui.DECOR_H, 360 + 1040)
        self.assertGreaterEqual(x, 2560)
        self.assertLessEqual(x + w + setup_ui.DECOR_W, 2560 + 1920)

    def test_tiny_screen_still_fits(self):
        w, h, x, y = setup_ui.fit_window(600, 900, (0, 0, 500, 300))
        self.assertLessEqual(w + setup_ui.DECOR_W, 500)
        self.assertLessEqual(h + setup_ui.DECOR_H, 300)



@unittest.skipIf(setup_ui is None, "needs tkinter")
class ShortScreen(unittest.TestCase):
    """The setup screen stays short: the command word only gets a line when there's something
    to say about it."""

    def screen(self, saved="Assistant"):
        from unittest import mock
        w = setup_ui.SetupWindow.__new__(setup_ui.SetupWindow)
        w.original = mock.Mock(keyword=saved)
        return w

    def test_nothing_under_an_unchanged_word(self):
        self.assertEqual(self.screen().word_message("Assistant"), ("", None))
        self.assertEqual(self.screen().word_message("assistant"), ("", None))

    def test_a_tip_once_its_changed(self):
        self.assertEqual(self.screen().word_message("Jarvis"),
                         (setup_ui.WORD_TRY_TIP, "Note.TLabel"))

    def test_problems_are_shown(self):
        msg, style = self.screen().word_message("two words")
        self.assertEqual(style, "Warn.TLabel")
        self.assertTrue(msg)

    def test_explanations_moved_to_the_voice_commands_window(self):
        self.assertFalse(hasattr(setup_ui, "PRIVACY_NOTE"))


if __name__ == "__main__":
    unittest.main()
