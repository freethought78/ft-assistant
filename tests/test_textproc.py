import unittest

from ft_assistant.textproc import (Command, build_hotwords, check_keyword, clean_text,
                                   parse_command, route)


class CleanText(unittest.TestCase):
    def test_credit_removed(self):
        self.assertEqual(clean_text("losing any of my stuff Closed Captioning by www.microsoft.com"),
                         "losing any of my stuff")
        self.assertEqual(clean_text("That works. Subtitles by the Amara.org community"), "That works.")
        self.assertEqual(clean_text("Good. Closed Captioning by www.microsoft.com Subtitles by the "
                                    "Amara.org community"), "Good.")

    def test_only_credit_or_hallucination(self):
        self.assertEqual(clean_text("Subtitles by the Amara.org community"), "")
        self.assertEqual(clean_text("Thank you."), "")
        self.assertEqual(clean_text("   "), "")
        self.assertEqual(clean_text(None), "")

    def test_normal_speech_kept(self):
        for s in ("Turn on the subtitles by default please",
                  "The captions by the speaker were wrong",
                  "Hello there, this is a normal sentence."):
            self.assertEqual(clean_text(s), s)


class ParseCommand(unittest.TestCase):
    def test_dictation(self):
        self.assertEqual(parse_command("Hello world."), Command("dictate", "Hello world."))
        self.assertEqual(parse_command("The assistant said hello."),
                         Command("dictate", "The assistant said hello."))
        self.assertEqual(parse_command("Assistants are useful."),
                         Command("dictate", "Assistants are useful."))
        self.assertEqual(parse_command("Assistant's job is easy."),
                         Command("dictate", "Assistant's job is easy."))
        self.assertEqual(parse_command(""), Command("dictate", ""))

    def test_assistant(self):
        # Forms Whisper produced in testing: capitalized, sometimes a comma or period.
        self.assertEqual(parse_command("Assistant, open the browser, and check my email"),
                         Command("assistant", "open the browser, and check my email"))
        self.assertEqual(parse_command("Assistant make a new project for my photos"),
                         Command("assistant", "make a new project for my photos"))
        self.assertEqual(parse_command("assistant. What's the weather?"),
                         Command("assistant", "What's the weather?"))
        self.assertEqual(parse_command("Assistant"), Command("assistant", ""))
        self.assertEqual(parse_command("Assistant."), Command("assistant", ""))

    def test_setup(self):
        for s in ("Assistant Setup", "Assistant setup.", "Assistant, set up.", "assistant set-up"):
            self.assertEqual(parse_command(s), Command("setup"), s)
        # More words after "setup" make it a normal request.
        self.assertEqual(parse_command("Assistant setup a new repo"),
                         Command("assistant", "setup a new repo"))


    def test_help_and_stop(self):
        for s in ("Assistant help", "Assistant, help.", "assistant Help!"):
            self.assertEqual(parse_command(s), Command("help"), s)
        for s in ("Assistant stop", "Assistant, stop.", "Assistant STOP!"):
            self.assertEqual(parse_command(s), Command("stop"), s)
        self.assertEqual(parse_command("Jarvis stop", "Jarvis"), Command("stop"))
        # More words make it a request, which goes to the assistant as usual.
        self.assertEqual(parse_command("Assistant, stop the server."),
                         Command("assistant", "stop the server."))
        self.assertEqual(parse_command("Assistant, help me write a test."),
                         Command("assistant", "help me write a test."))

    def test_new_topic(self):
        for s in ("Assistant new topic", "Assistant, new topic.", "assistant New-topic!"):
            self.assertEqual(parse_command(s), Command("new_topic", ""), s)
        # A request after a pause goes to the new conversation.
        self.assertEqual(parse_command("Assistant, new topic. Check the build."),
                         Command("new_topic", "Check the build."))
        self.assertEqual(parse_command("Assistant new topic, what's the weather?"),
                         Command("new_topic", "what's the weather?"))
        # Without a pause it's an ordinary request.
        self.assertEqual(parse_command("Assistant, new topic ideas for the blog."),
                         Command("assistant", "new topic ideas for the blog."))
        # No assistant ("Dictation only"): just typed.
        self.assertEqual(route("Assistant new topic", dictation_only=True).kind, "dictate")

    def test_undo(self):
        for s in ("Assistant undo", "Assistant, undo.", "assistant Undo!"):
            self.assertEqual(parse_command(s), Command("undo"), s)
        self.assertEqual(parse_command("Assistant, undo the last commit."),
                         Command("assistant", "undo the last commit."))
        # It works without an assistant too ("Dictation only").
        self.assertEqual(route("Assistant undo", dictation_only=True), Command("undo"))


class DictationOnly(unittest.TestCase):
    def test_keyword_is_plain_text_in_dictation_only(self):
        self.assertEqual(route("Assistant, open the browser.", dictation_only=True),
                         Command("dictate", "Assistant, open the browser."))
        self.assertEqual(route("Assistant", dictation_only=True), Command("dictate", "Assistant"))

    def test_setup_still_works_in_dictation_only(self):
        self.assertEqual(route("Assistant setup.", dictation_only=True), Command("setup"))
        self.assertEqual(route("Assistant help.", dictation_only=True), Command("help"))
        # No assistant to stop: typed like any other text.
        self.assertEqual(route("Assistant stop.", dictation_only=True),
                         Command("dictate", "Assistant stop."))

    def test_assistant_mode_unchanged(self):
        self.assertEqual(route("Assistant, open the browser.", dictation_only=False),
                         Command("assistant", "open the browser."))
        self.assertEqual(route("Hello there.", dictation_only=True), Command("dictate", "Hello there."))


class CommandWord(unittest.TestCase):
    def test_custom_word(self):
        self.assertEqual(parse_command("Jarvis, open the browser.", "Jarvis"),
                         Command("assistant", "open the browser."))
        self.assertEqual(parse_command("jarvis setup", "Jarvis"), Command("setup"))
        # With a custom word, "Assistant" is ordinary text.
        self.assertEqual(parse_command("Assistant, hello.", "Jarvis"),
                         Command("dictate", "Assistant, hello."))
        self.assertEqual(route("Jarvis, hello.", dictation_only=True, keyword="Jarvis"),
                         Command("dictate", "Jarvis, hello."))
        self.assertEqual(parse_command("Über, start", "über"), Command("assistant", "start"))

    def test_check_keyword(self):
        self.assertEqual(check_keyword("jarvis"), ("Jarvis", None, None))
        self.assertEqual(check_keyword(" Computer. "), ("Computer", None, None))
        for bad in ("", "two words", "R2D2", "x", "a" * 21, "hey!there"):
            word, error, _ = check_keyword(bad)
            self.assertIsNone(word, bad)
            self.assertTrue(error, bad)
        word, error, warning = check_keyword("okay")
        self.assertEqual((word, error), ("Okay", None))
        self.assertTrue(warning)


class Hotwords(unittest.TestCase):
    def test_keyword_hints_always_first(self):
        hints = ("Assistant, Assistant setup, Assistant help, Assistant stop, Assistant undo, "
                 "Assistant new topic")
        self.assertEqual(build_hotwords([]), hints)
        self.assertEqual(build_hotwords(["Discord", "Claude", "assistant", " "]),
                         hints + ", Discord, Claude")
        self.assertEqual(build_hotwords(["Claude"], "Jarvis"),
                         "Jarvis, Jarvis setup, Jarvis help, Jarvis stop, Jarvis undo, "
                         "Jarvis new topic, Claude")


if __name__ == "__main__":
    unittest.main()
