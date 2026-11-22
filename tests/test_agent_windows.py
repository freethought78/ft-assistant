import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ft_assistant import agent_windows

try:
    from ft_assistant import app          # needs numpy (FT Assistant's own Python has it)
except ImportError:
    app = None


class SavedWindows(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = Path(self.dir.name) / "ft-assistant-agent-windows.json"

    def tearDown(self):
        self.dir.cleanup()

    def test_round_trip_in_the_same_login(self):
        agent_windows.save(self.path, "boot/c1/:0", {"claude": 123})
        self.assertEqual(agent_windows.load(self.path, "boot/c1/:0"), {"claude": 123})

    def test_only_window_numbers_are_kept(self):
        agent_windows.save(self.path, "s", {"claude": 123})
        self.assertEqual(json.loads(self.path.read_text()), {"session": "s",
                                                             "windows": {"claude": 123}})

    def test_another_login_session_is_ignored(self):
        agent_windows.save(self.path, "boot/c1/:0", {"claude": 123})
        self.assertEqual(agent_windows.load(self.path, "boot/c2/:0"), {})

    def test_unknown_session_keeps_nothing(self):
        agent_windows.save(self.path, None, {"claude": 123})
        self.assertFalse(self.path.exists())
        self.assertEqual(agent_windows.load(self.path, None), {})

    def test_no_windows_left_removes_the_file(self):
        agent_windows.save(self.path, "s", {"claude": 123})
        agent_windows.save(self.path, "s", {})
        self.assertFalse(self.path.exists())

    def test_damaged_or_missing_file(self):
        self.assertEqual(agent_windows.load(self.path, "s"), {})
        self.path.write_text("{not json")
        self.assertEqual(agent_windows.load(self.path, "s"), {})
        self.path.write_text("[1, 2]")
        self.assertEqual(agent_windows.load(self.path, "s"), {})

    @unittest.skipIf(os.name == "nt", "Linux")
    def test_linux_keeps_it_in_the_runtime_folder_per_build(self):
        env = {"XDG_RUNTIME_DIR": self.dir.name,
               "FT_ASSISTANT_CONFIG_DIR": str(Path(self.dir.name) / "ft-assistant-dev")}
        with mock.patch.dict(os.environ, env):
            self.assertEqual(agent_windows.state_file(),
                             Path(self.dir.name) / "ft-assistant-dev-agent-windows.json")

    @unittest.skipIf(os.name == "nt", "Linux")
    def test_linux_login_session(self):
        from ft_assistant import platform_linux
        boot = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
        with mock.patch.dict(os.environ, {"XDG_SESSION_ID": "c1", "DISPLAY": ":0"}):
            self.assertEqual(platform_linux.login_session(), f"{boot}/c1/:0")


@unittest.skipIf(app is None, "numpy isn't installed")
class AfterARestart(unittest.TestCase):
    """FT Assistant restarted (an update) while its Claude Code window stayed open."""

    def make_app(self, saved):
        a = app.App.__new__(app.App)          # no engine, no key listener
        a.agent_window = dict(saved)
        a.our_windows = set(saved.values())
        a.titled = set(saved.values())
        a.window_file, a.login, a.windows_lock = None, None, app.threading.Lock()
        a.settings = mock.Mock(harness="claude", uses_assistant=True)
        return a

    def ask(self, a, title, focus=(1, "firefox", "Docs")):
        with mock.patch.object(app, "plat") as plat, \
                mock.patch.object(app.config, "load", return_value=a.settings), \
                mock.patch.object(app.harness, "open_session") as open_session, \
                mock.patch.object(app.threading, "Thread"):
            plat.is_terminal_class.side_effect = lambda c: c == "gnome-terminal-server"
            plat.terminal_windows.return_value = {9}
            plat.window_title.return_value = title
            plat.activate_window.return_value = True
            a.run_assistant("check the build", focus)
        return plat, open_session

    def test_the_open_window_gets_the_request(self):
        a = self.make_app({"claude": 9})
        plat, open_session = self.ask(a, "✳ Build checks")
        plat.activate_window.assert_called_once_with(9)
        plat.type_text.assert_called_once_with("check the build")
        open_session.assert_not_called()

    def test_a_reused_window_number_isnt_typed_into(self):
        # The Claude window was closed; a plain terminal now has its number.
        a = self.make_app({"claude": 9})
        plat, open_session = self.ask(a, "ft@MSI: ~")
        plat.type_text.assert_not_called()
        open_session.assert_called_once()
        self.assertEqual(a.agent_window, {})            # forgotten

    def test_a_reused_number_with_focus_on_it_isnt_the_assistant(self):
        a = self.make_app({"claude": 9})
        self.assertFalse(a.in_harness((9, "gnome-terminal-server", "ft@MSI: ~")))
        self.assertTrue(a.in_harness((9, "gnome-terminal-server", "✳ Build checks")))

    def test_a_new_window_counts_before_its_title_is_set(self):
        a = self.make_app({})
        a.agent_window, a.our_windows = {"claude": 9}, {9}        # just opened, not titled yet
        plat, open_session = self.ask(a, "claude --continue")
        plat.type_text.assert_called_once()
        open_session.assert_not_called()

    def test_once_titled_it_must_keep_the_title(self):
        a = self.make_app({})
        a.agent_window, a.our_windows = {"claude": 9}, {9}
        self.ask(a, "✳ Build checks")
        self.assertIn(9, a.titled)
        plat, open_session = self.ask(a, "ft@MSI: ~")
        plat.type_text.assert_not_called()
        open_session.assert_called_once()


if __name__ == "__main__":
    unittest.main()
