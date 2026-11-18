import sys
import unittest
from unittest import mock

from ft_assistant import gui


class SetupPython(unittest.TestCase):
    def setUp(self):
        gui._cached = None

    def tearDown(self):
        gui._cached = None

    def test_own_python_when_it_draws_smooth_fonts(self):
        with mock.patch.object(gui, "draws_smooth_fonts", return_value=True):
            self.assertEqual(gui.setup_python(), (sys.executable, []))

    def test_system_python_when_own_tk_is_plain(self):
        with mock.patch.object(gui, "draws_smooth_fonts", side_effect=lambda e: e == "/usr/bin/python3"), \
                mock.patch.object(gui.shutil, "which", return_value="/usr/bin/python3"), \
                mock.patch.object(gui, "vendor_dir", return_value="/v"):
            self.assertEqual(gui.setup_python(), ("/usr/bin/python3", ["/v"]))

    def test_fallback_to_own_python(self):
        with mock.patch.object(gui, "draws_smooth_fonts", return_value=False), \
                mock.patch.object(gui.shutil, "which", return_value="/usr/bin/python3"):
            self.assertEqual(gui.setup_python(), (sys.executable, []))
        gui._cached = None
        with mock.patch.object(gui, "draws_smooth_fonts", return_value=False), \
                mock.patch.object(gui.shutil, "which", return_value=None):
            self.assertEqual(gui.setup_python(), (sys.executable, []))


if __name__ == "__main__":
    unittest.main()
