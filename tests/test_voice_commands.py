import unittest
from unittest import mock

from ft_assistant import textproc, voice_commands

try:
    from ft_assistant import app          # needs numpy (FT Assistant's own Python has it)
except ImportError:
    app = None


class CommandList(unittest.TestCase):
    def test_lists_every_command_with_the_users_word(self):
        said = [say for say, _ in voice_commands.command_list("Jarvis")]
        self.assertEqual(said, ["Jarvis, ...", "Jarvis", "Jarvis new topic, ...", "Jarvis stop",
                                "Jarvis undo", "Jarvis setup", "Jarvis help"])

    def test_dictation_only_shows_only_what_works(self):
        said = [say for say, _ in voice_commands.command_list("Assistant", dictation_only=True)]
        self.assertEqual(said, ["Assistant undo", "Assistant setup", "Assistant help"])
        self.assertIn("choose one on the setup screen",
                      " ".join(voice_commands.notes("Assistant", dictation_only=True)))

    def test_good_to_know_has_the_privacy_note(self):
        notes = " ".join(voice_commands.notes("Jarvis"))
        self.assertIn("Dictation never leaves this computer", notes)
        self.assertIn("\"Jarvis\"", notes)
        self.assertIn("nothing you say is sent anywhere",
                      " ".join(voice_commands.notes("Jarvis", dictation_only=True)))

    def test_the_quiet_gap_is_explained(self):
        self.assertIn("After 15 quiet minutes, \"Assistant, ...\" starts a new conversation",
                      " ".join(voice_commands.notes("Assistant", quiet_gap=15)))
        self.assertNotIn("quiet", " ".join(voice_commands.notes("Assistant", quiet_gap=0)))
        self.assertNotIn("quiet", " ".join(voice_commands.notes("Assistant", True, 15)))

    def test_each_note_is_one_sentence(self):
        # Keep it simple: one sentence per note, nothing long to read.
        for dictation_only in (False, True):
            for line in voice_commands.notes("Assistant", dictation_only, quiet_gap=15):
                self.assertEqual(line.count(". "), 0, line)
                self.assertLess(len(line), 140, line)

    def test_stays_short(self):
        # FT Assistant should stay simple: at most about 7 voice commands, ever.
        self.assertLessEqual(len(voice_commands.COMMANDS), 7)

    def test_every_listed_command_is_understood(self):
        for say, _ in voice_commands.command_list("Assistant"):
            if say.endswith("..."):
                continue
            kind = textproc.parse_command(say).kind
            self.assertIn(kind, ("assistant", "setup", "help", "stop", "undo"), say)
            self.assertIn(say, textproc.keyword_hints("Assistant"))    # a Whisper hint too


@unittest.skipIf(app is None, "numpy isn't installed")
class Stop(unittest.TestCase):
    def make_app(self):
        a = app.App.__new__(app.App)          # no engine, no key listener
        a.our_windows, a.agent_window, a.commands_proc = set(), {}, None
        a.titled, a.window_file, a.login = set(), None, None
        a.windows_lock = app.threading.Lock()
        a.settings = mock.Mock(harness="opencode")
        return a

    def test_stop_in_the_assistant_window_presses_escape_there(self):
        a = self.make_app()
        with mock.patch.object(app, "plat") as plat, \
                mock.patch.object(app.harness, "harness_from_title", return_value="opencode"):
            plat.is_terminal_class.return_value = True
            a.stop_assistant((42, "gnome-terminal", "OC | session"))
        self.assertEqual(plat.press_escape.call_count, 2)       # OpenCode: "esc again to interrupt"
        plat.activate_window.assert_not_called()

    def test_claude_code_gets_one_escape(self):
        a = self.make_app()
        a.settings = mock.Mock(harness="claude")
        a.agent_window["claude"] = 9
        with mock.patch.object(app, "plat") as plat, \
                mock.patch.object(app.config, "load", return_value=a.settings):
            plat.is_terminal_class.return_value = False
            plat.terminal_windows.return_value = {9}
            plat.window_title.return_value = "✳ Long task"
            plat.activate_window.return_value = True
            a.stop_assistant((1, "firefox", "Docs"))
        plat.press_escape.assert_called_once()                   # a second would open "rewind"

    def test_stop_elsewhere_brings_the_assistant_forward_first(self):
        a = self.make_app()
        a.agent_window["opencode"] = 7
        with mock.patch.object(app, "plat") as plat, \
                mock.patch.object(app.config, "load", return_value=a.settings):
            plat.is_terminal_class.return_value = False
            plat.terminal_windows.return_value = {7}
            plat.window_title.return_value = "OC | Long task"
            plat.activate_window.return_value = True
            a.stop_assistant((1, "firefox", "Docs"))
        plat.activate_window.assert_called_once_with(7)
        self.assertEqual(plat.press_escape.call_count, 2)

    def test_stop_with_no_assistant_window_just_says_so(self):
        a = self.make_app()
        with mock.patch.object(app, "plat") as plat, \
                mock.patch.object(app.config, "load", return_value=a.settings):
            plat.is_terminal_class.return_value = False
            plat.terminal_windows.return_value = set()
            a.stop_assistant((1, "firefox", "Docs"))
        plat.press_escape.assert_not_called()
        plat.notify.assert_called_once()

    def test_help_opens_one_window(self):
        a = self.make_app()
        with mock.patch.object(app.subprocess, "Popen") as popen:
            popen.return_value.poll.return_value = None          # still open
            a.open_commands()
            a.open_commands()
        popen.assert_called_once()
        self.assertEqual(popen.call_args[0][0][1:], ["-m", "ft_assistant.voice_commands"])



@unittest.skipIf(app is None, "numpy isn't installed")
class Undo(unittest.TestCase):
    """ "<word> undo" deletes only what FT Assistant just typed, and only when that's safe."""

    @staticmethod
    def audio():
        return app.np.full(app.SAMPLE_RATE, 0.1, dtype=app.np.float32)    # 1 s, not silent

    def run_app(self, steps, presses=(0,), focus=(5, "gedit", "Notes")):
        a = app.App.__new__(app.App)
        a.settings = mock.Mock(dictation_only=False, keyword="Assistant", harness="claude")
        a.caps_trigger, a.last_typed, a.commands_proc = False, None, None
        counts = iter(presses)
        with mock.patch.object(app, "plat") as plat, \
                mock.patch.object(a, "engine", create=True) as engine:
            plat.input_count.side_effect = lambda: next(counts)
            for said, where in steps:
                engine.transcribe.return_value = said
                a.process(self.audio(), where or focus)
        return plat

    def test_undo_right_after_dictating(self):
        plat = self.run_app([("Hello there.", None), ("Assistant undo", None)], presses=(3, 3))
        plat.press_backspace.assert_called_once_with(len("Hello there. "))

    def test_not_after_typing_or_clicking(self):
        plat = self.run_app([("Hello there.", None), ("Assistant undo", None)], presses=(3, 4))
        plat.press_backspace.assert_not_called()
        plat.notify.assert_called_once()

    def test_not_when_typing_and_clicks_cant_be_checked(self):
        # Windows: a hook dropped by Windows (or no listener): never delete on a guess.
        a = app.App.__new__(app.App)
        a.last_typed = (5, 13, 3)
        with mock.patch.object(app, "plat") as plat:
            plat.input_count.return_value = 3
            plat.input_watch_ok.return_value = False
            a.undo((5, "gedit", "Notes"))
        plat.press_backspace.assert_not_called()
        plat.notify.assert_called_once()

    def test_not_in_another_window(self):
        plat = self.run_app([("Hello there.", None),
                             ("Assistant undo", (6, "firefox", "Docs"))], presses=(3, 3))
        plat.press_backspace.assert_not_called()

    def test_only_once(self):
        plat = self.run_app([("Hello there.", None), ("Assistant undo", None),
                             ("Assistant undo", None)], presses=(3, 3))
        plat.press_backspace.assert_called_once()
        plat.notify.assert_called_once_with("Nothing to undo.")

    def test_not_after_another_command(self):
        # "Assistant help" in between: the dictation is no longer the last thing done.
        with mock.patch.object(app.subprocess, "Popen"):
            plat = self.run_app([("Hello there.", None), ("Assistant help", None),
                                 ("Assistant undo", None)], presses=(3, 3))
        plat.press_backspace.assert_not_called()

    def test_nothing_typed_yet(self):
        plat = self.run_app([("Assistant undo", None)])
        plat.press_backspace.assert_not_called()
        plat.notify.assert_called_once_with("Nothing to undo.")

    def test_only_the_length_is_kept(self):
        a = app.App.__new__(app.App)
        with mock.patch.object(app, "plat") as plat, \
                mock.patch.object(a, "engine", create=True) as engine:
            a.settings = mock.Mock(dictation_only=False, keyword="Assistant")
            a.caps_trigger, a.last_typed = False, None
            plat.input_count.return_value = 1
            engine.transcribe.return_value = "Secret words."
            a.process(self.audio(), (5, "gedit", "Notes"))
        self.assertNotIn("Secret", repr(a.last_typed))



class InputWatch(unittest.TestCase):
    def test_windows_without_running_hooks_says_no(self):
        from ft_assistant import platform_windows
        self.assertFalse(platform_windows.input_watch_ok())     # sends nothing when not listening

    @unittest.skipIf(__import__("os").name == "nt", "Linux")
    def test_linux_only_while_listening(self):
        from ft_assistant import platform_linux
        self.assertFalse(platform_linux.input_watch_ok())


if __name__ == "__main__":
    unittest.main()
