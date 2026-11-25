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

    def test_clean_env_drops_the_starting_terminals_window(self):
        # Started from a terminal (the update window), FT Assistant inherits that window's
        # address; gnome-terminal then opens no new window while another one is open.
        env = harness.clean_env({
            "PATH": "/bin", "DISPLAY": ":0", "TERM": "xterm-256color",
            "GNOME_TERMINAL_SCREEN": "/org/gnome/Terminal/screen/gone",
            "GNOME_TERMINAL_SERVICE": ":1.1815", "VTE_VERSION": "7600", "WINDOWID": "1",
            "KONSOLE_DBUS_WINDOW": "/Windows/1", "WT_SESSION": "x"})
        self.assertEqual(env, {"PATH": "/bin", "DISPLAY": ":0", "TERM": "xterm-256color"})

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


class InstallingAnAssistant(unittest.TestCase):
    def test_linux_uses_each_projects_install_script(self):
        _, cmd = harness.install_plan("claude", windows=False)
        self.assertEqual(cmd, "curl -fsSL https://claude.ai/install.sh | bash")
        _, cmd = harness.install_plan("opencode", windows=False)
        self.assertEqual(cmd, "curl -fsSL https://opencode.ai/install | bash")
        which = lambda n: "/usr/bin/gnome-terminal" if n == "gnome-terminal" else None  # noqa: E731
        argv = harness.install_window_command("opencode", "Assistant", windows=False, which=which)
        self.assertEqual(argv[:3], ["gnome-terminal", argv[1], "--"])
        self.assertIn("opencode.ai/install", argv[-1])
        self.assertIn("Press Enter to close", argv[-1])

    def test_windows_picks_the_right_opencode_build(self):
        self.assertEqual(harness.opencode_windows_asset("AMD64", avx2=True), "opencode-windows-x64.zip")
        self.assertEqual(harness.opencode_windows_asset("AMD64", avx2=False),
                         "opencode-windows-x64-baseline.zip")
        self.assertEqual(harness.opencode_windows_asset("ARM64"), "opencode-windows-arm64.zip")

    def test_windows_opencode_needs_no_npm_and_no_website(self):
        with mock.patch.object(harness, "_has_avx2", return_value=True):
            source, script = harness.install_plan("opencode", windows=True)
            argv = harness.install_window_command("opencode", "Assistant", windows=True)
        url = harness.OPENCODE_DOWNLOAD + "opencode-windows-x64.zip"
        self.assertIn(url, source)
        self.assertNotIn("npm", script)
        self.assertEqual(argv[:6], ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                                    "-NoExit", "-EncodedCommand"])
        import base64
        ps = base64.b64decode(argv[6]).decode("utf-16-le")
        self.assertIn(f"'{url}'", ps)
        self.assertIn(".opencode\\bin", ps)
        self.assertIn("Expand-Archive", ps)
        self.assertIn("choose OpenCode and click Save", ps)

    def test_windows_claude_uses_its_own_installer(self):
        _, cmd = harness.install_plan("claude", windows=True)
        self.assertEqual(cmd, "irm https://claude.ai/install.ps1 | iex")


try:
    import tkinter  # noqa: F401
    from ft_assistant import setup_ui
except ImportError:
    setup_ui = None


@unittest.skipIf(setup_ui is None, "tkinter isn't installed")
class WatchingAnInstall(unittest.TestCase):
    def fake_screen(self, chosen=""):
        from types import SimpleNamespace
        scheduled = []
        var = SimpleNamespace(value=chosen)
        var.get = lambda: var.value
        var.set = lambda v: setattr(var, "value", v)
        screen = SimpleNamespace(installing={"opencode": 10 ** 12}, harness_var=var,
                                 root=SimpleNamespace(after=lambda ms, f: scheduled.append(ms)),
                                 _refresh=lambda: None)
        screen._watch_installs = lambda: setup_ui.SetupWindow._watch_installs(screen)
        return screen, scheduled

    def test_keeps_watching_until_it_turns_up_then_picks_it(self):
        screen, scheduled = self.fake_screen()
        with mock.patch.object(harness, "find_exe", return_value=None):
            screen._watch_installs()
        self.assertEqual(scheduled, [2000])                  # still waiting
        with mock.patch.object(harness, "find_exe", return_value="/x/opencode"):
            screen._watch_installs()
        self.assertEqual(screen.installing, {})
        self.assertEqual(screen.harness_var.get(), "opencode")
        self.assertEqual(scheduled, [2000])                  # stopped watching

    def test_never_overrides_an_existing_choice(self):
        screen, _ = self.fake_screen(chosen="claude")
        with mock.patch.object(harness, "find_exe", return_value="/x/opencode"):
            screen._watch_installs()
        self.assertEqual(screen.harness_var.get(), "claude")

    def test_gives_up_after_the_time_limit(self):
        screen, scheduled = self.fake_screen()
        screen.installing["opencode"] = 0
        with mock.patch.object(harness, "find_exe", return_value=None):
            screen._watch_installs()
        self.assertEqual(screen.installing, {})
        self.assertEqual(scheduled, [])
