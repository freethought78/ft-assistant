"""Conversations last as long as the assistant's window (the user's decision, 2026-11-25, in
place of a 15-minute timer): open window, the conversation goes on; closed window, the next
request starts a new one. Plus "<word> new topic", "<word> close" and "<word> send"."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ft_assistant import config, harness

try:
    from ft_assistant import app          # needs numpy (FT Assistant's own Python has it)
except ImportError:
    app = None


class Basics(unittest.TestCase):
    def test_throwaway_sessions_folder(self):
        with mock.patch.dict(os.environ, {"FT_ASSISTANT_SESSIONS_DIR": "/tmp/ft-test-sessions"}):
            self.assertEqual(config.sessions_dir(), Path("/tmp/ft-test-sessions"))

    def test_a_new_window_is_always_a_new_conversation(self):
        calls = []
        with tempfile.TemporaryDirectory() as home, \
                mock.patch.object(config, "sessions_dir", return_value=Path(home)), \
                mock.patch.object(harness, "find_exe", return_value="/usr/bin/claude"), \
                mock.patch.object(harness, "terminal_command", side_effect=lambda a, f: a):
            harness.open_session("claude", "hi", launcher=lambda cmd, **kw: calls.append(cmd))
        self.assertEqual(calls, [["/usr/bin/claude", "hi"]])          # never --continue

    def test_no_timer_setting(self):
        self.assertFalse(hasattr(config.Settings(), "quiet_gap_minutes"))

    def test_setup_keeps_settings_it_doesnt_show(self):
        src = (Path(config.__file__).parent / "setup_ui.py").read_text()
        self.assertIn("dataclasses.replace(self.original", src)


@unittest.skipIf(app is None, "numpy isn't installed")
class Conversations(unittest.TestCase):
    def make_app(self, open_window=None):
        a = app.App.__new__(app.App)
        a.settings = mock.Mock(harness="claude", uses_assistant=True)
        a.agent_window, a.our_windows, a.titled = {}, set(), set()
        a.window_file, a.login, a.windows_lock = None, None, app.threading.Lock()
        if open_window:
            a.agent_window["claude"], a.our_windows = open_window, {open_window}
        return a

    def run_it(self, a, call, open_windows=(), title="✳ Build checks", closes=True):
        typed = []
        windows = set(open_windows)
        with mock.patch.object(app, "plat") as plat, \
                mock.patch.object(app.config, "load", return_value=a.settings), \
                mock.patch.object(app.harness, "open_session",
                                  return_value=(mock.Mock(key="claude"), None)) as open_session, \
                mock.patch.object(app.threading, "Thread"), \
                mock.patch.object(app.time, "sleep"), \
                mock.patch.object(app, "CLOSE_WAIT", 0.01):
            plat.is_terminal_class.side_effect = lambda c: c == "gnome-terminal-server"
            plat.terminal_windows.side_effect = lambda: set(windows)
            plat.window_title.return_value = title
            plat.activate_window.return_value = True
            plat.type_text.side_effect = typed.append
            plat.press_escape.side_effect = lambda: typed.append("<Esc>")

            def enter():
                typed.append("<Enter>")
                if closes and typed[-2:-1] == ["/exit"]:
                    windows.clear()                    # the assistant quit: its window closes
            plat.press_enter.side_effect = enter
            call(a)
        return typed, open_session, plat

    def test_open_window_continues(self):
        typed, open_session, _ = self.run_it(
            self.make_app(9), lambda a: a.run_assistant("check it", (1, "firefox", "Docs")), {9})
        self.assertEqual(typed, ["check it", "<Enter>"])
        open_session.assert_not_called()

    def test_closed_window_starts_a_new_conversation(self):
        typed, open_session, _ = self.run_it(
            self.make_app(9), lambda a: a.run_assistant("check it", (1, "firefox", "Docs")))
        open_session.assert_called_once_with("claude", "check it")

    def test_just_the_word_with_no_window_opens_a_new_one(self):
        _, open_session, _ = self.run_it(
            self.make_app(), lambda a: a.run_assistant("", (1, "firefox", "Docs")))
        open_session.assert_called_once_with("claude", "")

    def test_new_topic_in_the_open_window(self):
        typed, _, _ = self.run_it(
            self.make_app(9), lambda a: a.run_assistant("", (1, "firefox", "Docs"), new=True), {9})
        self.assertEqual(typed, ["/clear", "<Enter>"])

    def test_new_topic_while_dictating_in_the_window(self):
        typed, _, _ = self.run_it(
            self.make_app(), lambda a: a.run_assistant(
                "next thing", (9, "gnome-terminal-server", "OC | Old"), new=True))
        self.assertEqual(typed, ["/new", "<Enter>", "next thing", "<Enter>"])   # OpenCode's

    def test_close_quits_the_assistant_in_its_window(self):
        a = self.make_app(9)
        typed, _, plat = self.run_it(a, lambda a: a.close_assistant((1, "firefox", "Docs")), {9})
        plat.activate_window.assert_called_once_with(9)
        self.assertEqual(typed, ["<Esc>", "/exit", "<Enter>"])
        plat.close_window.assert_not_called()                 # it closed by itself
        self.assertEqual(a.agent_window, {})                  # forgotten

    def test_close_from_inside_the_window(self):
        a = self.make_app(9)
        typed, _, _ = self.run_it(
            a, lambda a: a.close_assistant((9, "gnome-terminal-server", "✳ Build checks")), {9})
        self.assertEqual(typed, ["<Esc>", "/exit", "<Enter>"])

    def test_close_falls_back_to_closing_the_window(self):
        _, _, plat = self.run_it(self.make_app(9),
                                 lambda a: a.close_assistant((1, "firefox", "Docs")), {9},
                                 closes=False)
        plat.close_window.assert_called_once_with(9)

    def test_close_never_touches_another_claude_window(self):
        # Focus on one of the user's own Claude Code sessions; FT Assistant's window is closed.
        typed, _, plat = self.run_it(
            self.make_app(), lambda a: a.close_assistant((42, "gnome-terminal-server", "✳ My project")),
            {42})
        self.assertEqual(typed, [])
        plat.activate_window.assert_not_called()
        plat.close_window.assert_not_called()

    def test_close_with_no_window_does_nothing(self):
        typed, _, plat = self.run_it(self.make_app(),
                                     lambda a: a.close_assistant((1, "firefox", "Docs")))
        self.assertEqual(typed, [])
        plat.notify.assert_not_called()

    def test_send_presses_enter(self):
        a = self.make_app()
        a.caps_trigger, a.last_typed, a.commands_proc = False, None, None
        with mock.patch.object(app, "plat") as plat, \
                mock.patch.object(a, "engine", create=True) as engine:
            engine.transcribe.return_value = "Assistant send"
            a.settings = mock.Mock(dictation_only=False, keyword="Assistant", harness="claude")
            a.process(app.np.full(app.SAMPLE_RATE, 0.1, dtype=app.np.float32), (5, "gedit", "N"))
        plat.press_enter.assert_called_once()
        plat.type_text.assert_not_called()


if __name__ == "__main__":
    unittest.main()
