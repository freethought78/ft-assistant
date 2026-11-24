"""Conversation management, first part: "<word> new topic" and the quiet gap."""
import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from ft_assistant import config, harness

try:
    from ft_assistant import app          # needs numpy (FT Assistant's own Python has it)
except ImportError:
    app = None


class QuietGapSetting(unittest.TestCase):
    def load(self, data):
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.dict(os.environ, {"FT_ASSISTANT_CONFIG_DIR": d}):
            if data is not None:
                Path(d, "settings.json").write_text(json.dumps(data))
            return config.load().quiet_gap_minutes

    def test_on_by_default(self):
        self.assertEqual(self.load(None), 15)
        self.assertEqual(self.load({"harness": "claude"}), 15)

    def test_settings_file_can_change_or_turn_it_off(self):
        self.assertEqual(self.load({"quiet_gap_minutes": 30}), 30)
        self.assertEqual(self.load({"quiet_gap_minutes": 0}), 0)

    def test_bad_values_ignored(self):
        for bad in (-5, "15", True, 99999, 1.5):
            self.assertEqual(self.load({"quiet_gap_minutes": bad}), 15, bad)

    def test_saving_keeps_the_gap(self):
        # The setup screen saves only what it shows; a custom gap must survive it.
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.dict(os.environ, {"FT_ASSISTANT_CONFIG_DIR": d}):
            config.save(config.Settings(harness="claude", quiet_gap_minutes=30))
            self.assertEqual(config.load().quiet_gap_minutes, 30)

    def test_setup_keeps_settings_it_doesnt_show(self):
        src = (Path(config.__file__).parent / "setup_ui.py").read_text()
        self.assertIn("dataclasses.replace(self.original", src)
        self.assertNotIn("config.Settings(self.harness_var.get()", src)

    def test_throwaway_sessions_folder(self):
        with mock.patch.dict(os.environ, {"FT_ASSISTANT_SESSIONS_DIR": "/tmp/ft-test-sessions"}):
            self.assertEqual(config.sessions_dir(), Path("/tmp/ft-test-sessions"))


class LastActivity(unittest.TestCase):
    def test_claude_newest_conversation_file(self):
        with tempfile.TemporaryDirectory() as home:
            folder = Path(home) / "sessions"
            with mock.patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": str(Path(home) / ".claude")}):
                self.assertIsNone(harness.last_activity("claude", folder))
                proj = harness.claude_project_dir(folder)
                proj.mkdir(parents=True)
                old, new = proj / "a.jsonl", proj / "b.jsonl"
                old.write_text("{}"), new.write_text("{}")
                os.utime(old, (1000, 1000))
                os.utime(new, (2000, 2000))
                self.assertEqual(harness.last_activity("claude", folder), 2000)

    def test_new_session_skips_resume(self):
        calls = []
        with tempfile.TemporaryDirectory() as home, \
                mock.patch.object(config, "sessions_dir", return_value=Path(home)), \
                mock.patch.object(harness, "find_exe", return_value="/usr/bin/claude"), \
                mock.patch.object(harness, "last_conversation", return_value=True), \
                mock.patch.object(harness, "terminal_command", side_effect=lambda a, f: a):
            harness.open_session("claude", "hi", launcher=lambda cmd, **kw: calls.append(cmd))
            harness.open_session("claude", "hi", launcher=lambda cmd, **kw: calls.append(cmd),
                                 new=True)
        self.assertEqual(calls[0], ["/usr/bin/claude", "--continue", "hi"])
        self.assertEqual(calls[1], ["/usr/bin/claude", "hi"])


@unittest.skipIf(app is None, "numpy isn't installed")
class NewConversations(unittest.TestCase):
    def make_app(self, gap=15):
        a = app.App.__new__(app.App)
        a.settings = mock.Mock(harness="claude", uses_assistant=True, quiet_gap_minutes=gap)
        a.agent_window, a.our_windows, a.titled = {}, set(), set()
        a.window_file, a.login, a.windows_lock = None, None, app.threading.Lock()
        return a

    def ask(self, a, text, new=False, last=None, open_window=None, focus=(1, "firefox", "Docs")):
        typed = []
        if open_window:
            a.agent_window["claude"], a.our_windows = open_window, {open_window}
        with mock.patch.object(app, "plat") as plat, \
                mock.patch.object(app.config, "load", return_value=a.settings), \
                mock.patch.object(app.harness, "last_activity", return_value=last), \
                mock.patch.object(app.harness, "open_session",
                                  return_value=(mock.Mock(key="claude"), None)) as open_session, \
                mock.patch.object(app.threading, "Thread"), \
                mock.patch.object(app.time, "sleep"):
            plat.is_terminal_class.side_effect = lambda c: c == "gnome-terminal-server"
            plat.terminal_windows.return_value = {open_window} if open_window else set()
            plat.window_title.return_value = "✳ Build checks"
            plat.activate_window.return_value = True
            plat.type_text.side_effect = typed.append
            plat.press_enter.side_effect = lambda: typed.append("<Enter>")
            a.run_assistant(text, focus, new=new)
        return typed, open_session

    def test_recent_activity_continues(self):
        typed, open_session = self.ask(self.make_app(), "check it", last=time.time() - 60)
        open_session.assert_called_once_with("claude", "check it", new=False)

    def test_after_the_quiet_gap_a_new_conversation(self):
        typed, open_session = self.ask(self.make_app(), "check it", last=time.time() - 16 * 60)
        open_session.assert_called_once_with("claude", "check it", new=True)

    def test_gap_off(self):
        typed, open_session = self.ask(self.make_app(gap=0), "check it", last=0)
        open_session.assert_called_once_with("claude", "check it", new=False)

    def test_just_opening_the_window_never_starts_over(self):
        # "Assistant" alone shows the current conversation, however old.
        typed, open_session = self.ask(self.make_app(), "", last=0)
        open_session.assert_called_once_with("claude", "", new=False)

    def test_open_window_after_the_gap_clears_it_first(self):
        typed, open_session = self.ask(self.make_app(), "check it", last=0, open_window=9)
        self.assertEqual(typed, ["/clear", "<Enter>", "check it", "<Enter>"])
        open_session.assert_not_called()

    def test_new_topic_in_the_open_window(self):
        typed, _ = self.ask(self.make_app(), "", new=True, last=time.time(), open_window=9)
        self.assertEqual(typed, ["/clear", "<Enter>"])

    def test_new_topic_while_dictating_in_the_window(self):
        a = self.make_app()
        typed, _ = self.ask(a, "next thing", new=True, last=time.time(),
                            focus=(9, "gnome-terminal-server", "OC | Old"))
        self.assertEqual(typed, ["/new", "<Enter>", "next thing", "<Enter>"])   # OpenCode's

    def test_dictating_in_the_window_ignores_the_gap(self):
        typed, open_session = self.ask(self.make_app(), "go on", last=0,
                                       focus=(9, "gnome-terminal-server", "✳ Old"))
        self.assertEqual(typed, ["go on", "<Enter>"])
        open_session.assert_not_called()


if __name__ == "__main__":
    unittest.main()
