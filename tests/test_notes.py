"""Conversation notes: on or off from the setup screen, and never deleted by turning off."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ft_assistant import config, notes, voice_commands


class OnOff(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name) / "FT Assistant sessions"

    def tearDown(self):
        self.tmp.cleanup()

    def text(self, name):
        return (self.dir / name).read_text(encoding="utf-8")

    def test_on_writes_instructions_for_both_assistants(self):
        notes.apply(self.dir, True)
        for name in notes.FILES:
            self.assertIn("read notes/INDEX.md", self.text(name))
        self.assertTrue((self.dir / "notes" / "INDEX.md").exists())

    def test_a_support_for_the_assistants_memory_not_a_second_one(self):
        notes.apply(self.dir, True)
        for name in notes.FILES:
            self.assertIn("not a second memory", self.text(name))
            self.assertIn("log of work", self.text(name))

    def test_where_earlier_conversations_are(self):
        from ft_assistant import harness
        with mock.patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": "/home/u/.claude"}):
            notes.apply(self.dir, True)
        self.assertIn(str(harness.claude_project_dir(self.dir, "/home/u")), self.text("CLAUDE.md"))
        self.assertNotIn(".jsonl", self.text("AGENTS.md"))       # OpenCode keeps them elsewhere

    def test_off_keeps_every_note_and_on_brings_them_back(self):
        notes.apply(self.dir, True)
        note = self.dir / "notes" / "build.md"
        note.write_text("How the build works.")
        notes.apply(self.dir, False)
        self.assertEqual(note.read_text(), "How the build works.")          # never deleted
        self.assertIn("turned off", self.text("CLAUDE.md"))
        self.assertNotIn("read notes/INDEX.md", self.text("AGENTS.md"))
        notes.apply(self.dir, True)
        self.assertIn("read notes/INDEX.md", self.text("CLAUDE.md"))
        self.assertTrue(note.exists())

    def test_the_users_own_text_is_kept(self):
        self.dir.mkdir(parents=True)
        (self.dir / "CLAUDE.md").write_text("Always answer briefly.\n")
        notes.apply(self.dir, True)
        notes.apply(self.dir, False)
        text = self.text("CLAUDE.md")
        self.assertTrue(text.startswith("Always answer briefly.\n"))
        self.assertEqual(text.count(notes.START), 1)                         # one block only

    def test_off_creates_nothing_where_notes_never_were(self):
        notes.apply(self.dir, False)
        self.assertFalse(self.dir.exists())

    def test_nothing_rewritten_when_unchanged(self):
        notes.apply(self.dir, True)
        before = os.stat(self.dir / "CLAUDE.md").st_mtime_ns
        os.utime(self.dir / "CLAUDE.md", ns=(1, 1))
        notes.apply(self.dir, True)
        self.assertEqual(os.stat(self.dir / "CLAUDE.md").st_mtime_ns, 1)
        self.assertNotEqual(before, 1)

    def test_an_existing_index_is_kept(self):
        (self.dir / "notes").mkdir(parents=True)
        (self.dir / "notes" / "INDEX.md").write_text("- [Build](build.md): how it works\n")
        notes.apply(self.dir, True)
        self.assertEqual(self.text("notes/INDEX.md"), "- [Build](build.md): how it works\n")


class Setting(unittest.TestCase):
    def load(self, data):
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.dict(os.environ, {"FT_ASSISTANT_CONFIG_DIR": d}):
            Path(d, "settings.json").write_text(json.dumps(data))
            return config.load()

    def test_on_by_default(self):
        self.assertTrue(config.Settings().conversation_notes)
        self.assertTrue(self.load({}).conversation_notes)

    def test_off_kept(self):
        self.assertFalse(self.load({"conversation_notes": False}).conversation_notes)
        self.assertTrue(self.load({"conversation_notes": "no"}).conversation_notes)   # ignored

    def test_saving_keeps_settings_the_screen_doesnt_show(self):
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.dict(os.environ, {"FT_ASSISTANT_CONFIG_DIR": d}):
            config.save(config.Settings(harness="claude", quiet_gap_minutes=30,
                                        conversation_notes=False))
            s = config.load()
        self.assertEqual((s.quiet_gap_minutes, s.conversation_notes), (30, False))


class Explained(unittest.TestCase):
    def test_good_to_know_says_where_and_how_to_turn_off(self):
        text = " ".join(voice_commands.notes("Assistant", conversation_notes=True))
        self.assertIn("FT Assistant sessions", text)
        self.assertIn("setup screen", text)
        self.assertNotIn("notes in", " ".join(voice_commands.notes("Assistant")))


if __name__ == "__main__":
    unittest.main()
