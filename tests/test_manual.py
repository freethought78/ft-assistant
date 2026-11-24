"""The README on GitHub is the complete manual (the user's decision, 2026-11-24): every voice
command and every setting without a control on the setup screen must be in it. The release steps
in CLAUDE.md say to bring it up to date before each release; this catches what's easy to miss."""
import dataclasses
import unittest
from pathlib import Path

from ft_assistant import config, voice_commands

README = (Path(__file__).resolve().parent.parent / "README.md").read_text(encoding="utf-8")
# Settings the setup screen shows (anything else needs explaining in the manual).
ON_THE_SETUP_SCREEN = {"harness", "trigger", "keyword"}


class Manual(unittest.TestCase):
    def test_every_voice_command_is_in_it(self):
        for say, _ in voice_commands.command_list("Assistant"):
            spoken = say.removesuffix("...").rstrip(", ")
            self.assertIn(f'"{spoken}', README, f"voice command {say!r} missing from README.md")

    def test_hidden_settings_are_explained(self):
        for field in dataclasses.fields(config.Settings):
            if field.name not in ON_THE_SETUP_SCREEN:
                self.assertIn(f'"{field.name}"', README, f"setting {field.name} missing")

    def test_the_setup_screens_manual_button_points_here(self):
        try:
            from ft_assistant import setup_ui
        except ImportError:
            self.skipTest("needs tkinter")
        self.assertTrue(setup_ui.MANUAL_URL.endswith("#readme"))


if __name__ == "__main__":
    unittest.main()
