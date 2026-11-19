import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ft_assistant import config, harness


class HarnessCommands(unittest.TestCase):
    def test_argv(self):
        folder = Path("/home/u/FT Assistant sessions")
        self.assertEqual(harness.HARNESSES["claude"].argv(folder, "fix it"), ["claude", "fix it"])
        self.assertEqual(harness.HARNESSES["claude"].argv(folder, ""), ["claude"])
        self.assertEqual(harness.HARNESSES["opencode"].argv(folder, "fix it"),
                         ["opencode", str(folder), "--prompt", "fix it"])
        self.assertEqual(harness.HARNESSES["opencode"].argv(folder, ""), ["opencode", str(folder)])

    def test_argv_resume(self):
        folder = Path("/f")
        self.assertEqual(harness.HARNESSES["claude"].argv(folder, "go on", True),
                         ["claude", "--continue", "go on"])
        self.assertEqual(harness.HARNESSES["claude"].argv(folder, "", True), ["claude", "--continue"])
        self.assertEqual(harness.HARNESSES["opencode"].argv(folder, "go on", "ses_1"),
                         ["opencode", "/f", "--session", "ses_1", "--prompt", "go on"])

    def test_last_conversation_claude(self):
        with tempfile.TemporaryDirectory() as home, \
                mock.patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": str(Path(home) / ".claude")}):
            folder = "/home/u/FT Assistant sessions"
            self.assertIsNone(harness.last_conversation("claude", folder))
            d = harness.claude_project_dir(folder)
            self.assertEqual(d.name, "-home-u-FT-Assistant-sessions")
            d.mkdir(parents=True)
            (d / "abc.jsonl").write_text("{}")
            self.assertTrue(harness.last_conversation("claude", folder))

    def test_last_conversation_opencode(self):
        import sqlite3
        with tempfile.TemporaryDirectory() as home, \
                mock.patch.object(harness.Path, "home", return_value=Path(home)):
            self.assertIsNone(harness.last_conversation("opencode", "/s"))
            db = Path(home, ".local/share/opencode/opencode.db")
            db.parent.mkdir(parents=True)
            con = sqlite3.connect(db)
            con.execute("create table session (id text, directory text, parent_id text, "
                        "time_archived integer, time_updated integer)")
            con.executemany("insert into session values (?,?,?,?,?)", [
                ("old", "/s", None, None, 1), ("new", "/s", None, None, 5),
                ("child", "/s", "new", None, 9), ("gone", "/s", None, 3, 8),
                ("other", "/elsewhere", None, None, 10)])
            con.commit()
            con.close()
            self.assertEqual(harness.last_conversation("opencode", "/s"), "new")
            self.assertIsNone(harness.last_conversation("opencode", "/nothing"))

    def test_terminal_command(self):
        which_gnome = lambda name: "/usr/bin/" + name if name == "gnome-terminal" else None  # noqa: E731
        self.assertEqual(harness.terminal_command(["claude", "hi"], "/f", which=which_gnome),
                         ["gnome-terminal", "--working-directory=/f", "--", "claude", "hi"])
        which_xterm = lambda name: "/usr/bin/xterm" if name == "xterm" else None  # noqa: E731
        self.assertEqual(harness.terminal_command(["claude"], "/f", which=which_xterm),
                         ["xterm", "-e", "claude"])
        with self.assertRaises(RuntimeError):
            harness.terminal_command(["claude"], "/f", which=lambda n: None)

    def test_clean_env(self):
        env = harness.clean_env({"PATH": "/bin", "CLAUDECODE": "1", "CLAUDE_CODE_CHILD_SESSION": "x",
                                 "ANTHROPIC_API_KEY": "k", "HOME": "/h"})
        self.assertEqual(env, {"PATH": "/bin", "HOME": "/h"})

    def test_titles(self):
        self.assertEqual(harness.harness_from_title("OC | Fix the build"), "opencode")
        self.assertEqual(harness.harness_from_title("✳ FT Assistant title test"), "claude")
        self.assertEqual(harness.harness_from_title("Claude Code"), "claude")
        self.assertIsNone(harness.harness_from_title("ft@MSI: ~/repos"))
        self.assertIsNone(harness.harness_from_title(""))

    def test_open_session_uses_neutral_folder_and_clean_env(self):
        calls = []
        with tempfile.TemporaryDirectory() as home, \
                mock.patch.object(config, "sessions_dir", return_value=Path(home) / "FT Assistant sessions"), \
                mock.patch.object(harness, "find_exe", return_value="/usr/bin/claude"), \
                mock.patch.object(harness, "terminal_command", side_effect=lambda a, f: ["term", "--"] + a), \
                mock.patch.dict(os.environ, {"CLAUDECODE": "1", "PATH": "/bin"}):
            harness.open_session("claude", "hello", launcher=lambda cmd, **kw: calls.append((cmd, kw)))
            self.assertTrue((Path(home) / "FT Assistant sessions").is_dir())
        cmd, kw = calls[0]
        self.assertEqual(cmd, ["term", "--", "/usr/bin/claude", "hello"])   # full path
        self.assertTrue(kw["cwd"].endswith("FT Assistant sessions"))
        self.assertNotIn("CLAUDECODE", kw["env"])
        self.assertEqual(kw["env"]["PATH"].split(os.pathsep)[0], "/usr/bin")

    def test_found_in_nvm_when_not_on_search_path(self):
        # Installed with npm under nvm, and the app was started at login (no ~/.bashrc).
        with tempfile.TemporaryDirectory() as home:
            for v in ("v18.20.1", "v24.19.0", "v9.0.0"):
                b = Path(home, ".nvm", "versions", "node", v, "bin")
                b.mkdir(parents=True)
                exe = b / "claude"
                exe.write_text("#!/bin/sh\n")
                exe.chmod(0o755)
            dirs = harness.install_dirs(home=home, env={}, windows=False)
            nvm_dirs = [d.parent.name for d in dirs if ".nvm" in str(d)]
            self.assertEqual(nvm_dirs, ["v24.19.0", "v18.20.1", "v9.0.0"])   # newest first
            self.assertIn(Path(home, ".local", "bin"), dirs)
            self.assertIn(Path(home, ".opencode", "bin"), dirs)
            with mock.patch.dict(os.environ, {"PATH": "/nonexistent"}):
                found = harness.find_exe(harness.HARNESSES["claude"], dirs=dirs)
            self.assertEqual(found, str(Path(home, ".nvm", "versions", "node", "v24.19.0", "bin",
                                             "claude")))
            with mock.patch.dict(os.environ, {"PATH": "/nonexistent"}):
                self.assertIsNone(harness.find_exe(harness.HARNESSES["opencode"], dirs=dirs))

    def test_search_path_wins(self):
        which = lambda name, path=None: "/usr/bin/claude" if path is None else None  # noqa: E731
        self.assertEqual(harness.find_exe(harness.HARNESSES["claude"], which=which, dirs=[]),
                         "/usr/bin/claude")

    def test_windows_install_dirs(self):
        dirs = harness.install_dirs(home=r"C:\Users\u", env={"APPDATA": r"C:\Users\u\AppData\Roaming"},
                                    windows=True)
        self.assertIn(Path(r"C:\Users\u\AppData\Roaming") / "npm", dirs)
        self.assertIn(Path(r"C:\Users\u") / ".local" / "bin", dirs)

    def test_with_dir_on_path(self):
        env = harness.with_dir_on_path({"PATH": os.pathsep.join(["/usr/bin", "/bin"])}, "/opt/x")
        self.assertEqual(env["PATH"], os.pathsep.join(["/opt/x", "/usr/bin", "/bin"]))
        again = harness.with_dir_on_path(env, "/opt/x")
        self.assertEqual(again["PATH"], env["PATH"])

    def test_open_session_missing_cli(self):
        with mock.patch.object(harness, "find_exe", return_value=None):
            with self.assertRaises(RuntimeError):
                harness.open_session("opencode", "x", launcher=lambda *a, **k: None)


class Settings(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = mock.patch.dict(os.environ, {"FT_ASSISTANT_CONFIG_DIR": self.tmp.name})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def test_defaults(self):
        s = config.load()
        self.assertEqual(s.harness, "")
        self.assertFalse(s.harness_chosen)
        self.assertEqual(s.trigger, {"type": "key", "keysym": "Caps_Lock"})

    def test_roundtrip(self):
        s = config.Settings(harness="opencode", trigger={"type": "button", "button": 12})
        config.save(s)
        self.assertEqual(config.load(), s)

    def test_dictation_only(self):
        config.save(config.Settings(harness="none"))
        s = config.load()
        self.assertTrue(s.harness_chosen)
        self.assertTrue(s.dictation_only)
        self.assertFalse(s.uses_assistant)
        self.assertTrue(config.Settings(harness="claude").uses_assistant)
        self.assertFalse(config.Settings(harness="").harness_chosen)

    def test_keyword(self):
        self.assertEqual(config.load().keyword, "Assistant")
        config.save(config.Settings(harness="claude", keyword="Jarvis"))
        self.assertEqual(config.load().keyword, "Jarvis")
        Path(self.tmp.name, "settings.json").write_text(json.dumps({"keyword": "two words"}))
        self.assertEqual(config.load().keyword, "Assistant")

    def test_bad_values_fall_back(self):
        Path(self.tmp.name, "settings.json").write_text(json.dumps(
            {"harness": "gemini", "trigger": {"type": "button", "button": 1}}))
        s = config.load()
        self.assertEqual(s.harness, "")
        self.assertEqual(s.trigger, config.DEFAULT_TRIGGER)
        Path(self.tmp.name, "settings.json").write_text("not json")
        self.assertEqual(config.load(), config.Settings())


if __name__ == "__main__":
    unittest.main()
