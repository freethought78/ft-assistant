import unittest

from ft_assistant.textproc import Command, clean_text, parse_command


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


if __name__ == "__main__":
    unittest.main()
