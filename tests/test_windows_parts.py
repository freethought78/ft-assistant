"""The Windows layer's pure parts, tested on Linux (the rest is tested in the Bottles bottle)."""
import subprocess
import sys
import unittest

from ft_assistant import harness
from ft_assistant import platform_windows as w


class Keys(unittest.TestCase):
    def test_names_round_trip(self):
        for name in ("Caps_Lock", "Scroll_Lock", "Pause", "Insert", "Menu", "F13", "F24", "a",
                     "z", "5", "KP_3", "Super_L", "Escape"):
            self.assertEqual(w.name_for(w.vk_for(name)), name)
        self.assertEqual(w.vk_for("Caps_Lock"), 0x14)
        self.assertEqual(w.vk_for("F13"), 0x7C)
        self.assertEqual(w.name_for(0xE9), "VK_0xe9")
        self.assertEqual(w.vk_for("VK_0xe9"), 0xE9)
        self.assertIsNone(w.vk_for("NoSuchKey"))

    def test_side_buttons(self):
        self.assertEqual(w.xbutton_number(1 << 16), 8)
        self.assertEqual(w.xbutton_number(2 << 16), 9)


class Capture(unittest.TestCase):
    def k(self, name):
        return {"type": "key", "keysym": name}

    def test_wine_lock_sync_around_the_real_key(self):
        k = self.k
        # Seen in the bottle with Num Lock on: the real key sits between two synced Num_Locks.
        self.assertEqual(w.pick_captured([(0, k("Num_Lock")), (0.002, k("Pause")),
                                          (0.006, k("Num_Lock"))]), k("Pause"))
        self.assertEqual(w.pick_captured([(0, k("Num_Lock")), (0.001, k("Scroll_Lock")),
                                          (0.006, k("Num_Lock"))]), k("Scroll_Lock"))

    def test_single_presses(self):
        k = self.k
        self.assertEqual(w.pick_captured([(0, k("Num_Lock"))]), k("Num_Lock"))
        self.assertEqual(w.pick_captured([(0, k("Caps_Lock"))]), k("Caps_Lock"))
        self.assertEqual(w.pick_captured([(0, {"type": "button", "button": 8})]),
                         {"type": "button", "button": 8})
        self.assertIsNone(w.pick_captured([]))


class Typing(unittest.TestCase):
    def test_unicode_and_newlines(self):
        ev = w.key_events("Hé\n")
        self.assertEqual(ev[0], (0, ord("H"), w.KEYEVENTF_UNICODE))
        self.assertEqual(ev[1], (0, ord("H"), w.KEYEVENTF_UNICODE | w.KEYEVENTF_KEYUP))
        self.assertEqual(ev[2][1], ord("é"))
        self.assertEqual(ev[4:], [(0x0D, 0, 0), (0x0D, 0, w.KEYEVENTF_KEYUP)])

    def test_characters_outside_the_bmp(self):
        ev = w.key_events("😀")                    # two UTF-16 units, each down + up
        self.assertEqual(len(ev), 4)
        self.assertEqual([e[1] for e in ev[::2]], [0xD83D, 0xDE00])


class WindowsTerminal(unittest.TestCase):
    def test_never_through_wt(self):
        # wt.exe re-parses its command line: it drops the quotes around a folder with spaces and
        # splits on ";". The program is started directly instead, arguments untouched.
        which = {"wt": r"C:\wt.exe", "opencode": r"C:\Users\u\.opencode\bin\opencode.exe"}.get
        folder = r"C:\Users\u\FT Assistant sessions"
        cmd = harness.terminal_command(["opencode", folder, "--prompt", "fix it; then test"],
                                       folder, which=which, windows=True)
        self.assertEqual(cmd, [r"C:\Users\u\.opencode\bin\opencode.exe", folder, "--prompt",
                               "fix it; then test"])
        self.assertEqual(subprocess.list2cmdline(cmd),
                         r'C:\Users\u\.opencode\bin\opencode.exe "C:\Users\u\FT Assistant sessions" '
                         r'--prompt "fix it; then test"')

    def test_plain_console(self):
        which = {"opencode": r"C:\npm\opencode.cmd"}.get
        cmd = harness.terminal_command(["opencode", r"C:\S", "--prompt", "hi"], r"C:\S",
                                       which=which, windows=True)
        self.assertEqual(cmd, [r"C:\npm\opencode.cmd", r"C:\S", "--prompt", "hi"])

    def test_agent_uses_its_own_console(self):
        # NUL as stdin/stdout made OpenCode quit as soon as its window opened.
        self.assertEqual(harness.std_handles(windows=True), {})
        self.assertEqual(harness.new_window_kwargs(["x"])["creationflags"] & 0x10, 0x10) \
            if sys.platform == "win32" else None
        self.assertIn("stdin", harness.std_handles(windows=False))

    def test_terminal_classes(self):
        self.assertTrue(w.is_terminal_class("CASCADIA_HOSTING_WINDOW_CLASS"))
        self.assertTrue(w.is_terminal_class("ConsoleWindowClass"))
        self.assertFalse(w.is_terminal_class("Chrome_WidgetWin_1"))


if __name__ == "__main__":
    unittest.main()
