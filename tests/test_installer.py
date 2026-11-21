import importlib.util
import io
import os
import shutil
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("ft_install", REPO / "installer" / "install.py")
inst = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inst)


class Installer(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = Path(self.tmp.name)
        self.dir = t / "install"
        self.dir.mkdir()
        self.env = mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": str(t / "config"),
                                                "XDG_DATA_HOME": str(t / "data"),
                                                "FT_ASSISTANT_SOURCE": ""})
        self.env.start()
        # Most tests are about an install that already has FT Assistant's own Python.
        self.own_python = mock.patch.object(inst, "runtime_ok", return_value=True)
        self.own_python.start()

    def tearDown(self):
        self.own_python.stop()
        self.env.stop()
        self.tmp.cleanup()

    def test_fetch_app_from_folder_keeps_previous(self):
        inst.fetch_app(self.dir, str(REPO))
        self.assertTrue((self.dir / "app" / "ft_assistant" / "app.py").exists())
        self.assertFalse(any((self.dir / "app").rglob("__pycache__")))
        inst.fetch_app(self.dir, str(REPO))
        self.assertTrue((self.dir / "app.previous" / "ft_assistant" / "app.py").exists())

    def test_fetch_app_from_github_style_zip(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("freethought78-ft-assistant-abc123/README.md", "x")
            z.writestr("freethought78-ft-assistant-abc123/ft_assistant/__init__.py", "v = 1\n")
            z.writestr("freethought78-ft-assistant-abc123/ft_assistant/app.py", "# app\n")
        zpath = Path(self.tmp.name, "rel.zip")
        zpath.write_bytes(buf.getvalue())
        inst.fetch_app(self.dir, str(zpath))
        self.assertEqual((self.dir / "app" / "ft_assistant" / "__init__.py").read_text(), "v = 1\n")
        self.assertFalse((self.dir / "app" / "README.md").exists())

    def test_fetch_app_keeps_the_release_installer(self):
        inst.fetch_app(self.dir, str(REPO))
        self.assertEqual((self.dir / "install.py.new").read_text(),
                         (REPO / "installer" / "install.py").read_text())
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("x-ft-assistant-1/ft_assistant/__init__.py", "")
            z.writestr("x-ft-assistant-1/installer/install.py", "# new installer\n")
        zpath = Path(self.tmp.name, "rel.zip")
        zpath.write_bytes(buf.getvalue())
        inst.fetch_app(self.dir, str(zpath))
        self.assertEqual((self.dir / "install.py.new").read_text(), "# new installer\n")

    def test_update_hands_over_to_the_new_installer(self):
        (self.dir / "install.py").write_text("# old installer\n")
        inst.save_manifest(self.dir, {"gpu": False, "model": "m", "gpu_libs": "pip"})
        calls = []
        fake = lambda cmd, **kw: (calls.append(cmd), mock.Mock(returncode=0))[1]  # noqa: E731
        with mock.patch.object(inst, "stop_running_app"), \
                mock.patch.object(inst.subprocess, "run", side_effect=fake):
            with self.assertRaises(SystemExit) as cm:
                inst.main(["update", "--dir", str(self.dir), "--source", str(REPO), "--no-start"])
        self.assertEqual(cm.exception.code, 0)
        self.assertEqual((self.dir / "install.py").read_text(),
                         (REPO / "installer" / "install.py").read_text())
        self.assertEqual((self.dir / "install.py.previous").read_text(), "# old installer\n")
        self.assertEqual(calls[0][1:], [str(self.dir / "install.py"), "finish-update", "--dir",
                                        str(self.dir), "--no-start"])

    def test_finish_update_rolls_back_on_failure(self):
        (self.dir / "app" / "ft_assistant").mkdir(parents=True)
        (self.dir / "app.previous" / "ft_assistant").mkdir(parents=True)
        (self.dir / "app.previous" / "ft_assistant" / "old.py").write_text("old")
        (self.dir / "install.py").write_text("new")
        (self.dir / "install.py.previous").write_text("old")
        inst.save_manifest(self.dir, {"gpu": False, "model": "m"})
        with mock.patch.object(inst, "install_packages", side_effect=inst.PackagesFailed("x")), \
                mock.patch.object(inst, "start_app"):
            with self.assertRaises(SystemExit):
                inst.main(["finish-update", "--dir", str(self.dir)])
        self.assertTrue((self.dir / "app" / "ft_assistant" / "old.py").exists())
        self.assertEqual((self.dir / "install.py").read_text(), "old")

    def test_old_settings_launcher_removed_but_never_a_real_setup_file(self):
        # Before 0.2.5 the settings launcher was ft-assistant-setup(.cmd); on Windows that's the
        # same name as the downloaded setup file, which may have been saved here.
        old = self.dir / "ft-assistant-setup"
        old.write_text("#!/bin/bash\n# Written by the FT Assistant installer.\n"
                       'exec "py" -m ft_assistant.open_setup "$@"\n')
        launchers = inst.write_launchers(self.dir, gpu=False, model="small.en")
        self.assertFalse(old.exists())
        self.assertIn("-m ft_assistant.open_setup", launchers["ft-assistant-settings"].read_text())
        old.write_text((REPO / "installer" / "setup-template.cmd").read_text())   # a setup file
        inst.write_launchers(self.dir, gpu=False, model="small.en")
        self.assertTrue(old.exists())

    def test_update_rewrites_menu_entries_and_keeps_login_choice(self):
        inst.save_manifest(self.dir, {"gpu": False, "model": "m"})
        old_launchers = inst.write_launchers(self.dir, gpu=False, model="m")
        inst.write_shortcuts(old_launchers, autostart=False)       # user has no login entry
        setup_entry = Path(self.tmp.name) / "data" / "applications" / "ft-assistant-setup.desktop"
        setup_entry.write_text("Exec=/old/ft-assistant-setup\n")
        with mock.patch.object(inst, "install_packages"), mock.patch.object(inst, "start_app"):
            inst.main(["finish-update", "--dir", str(self.dir)])
        self.assertIn("ft-assistant-settings", setup_entry.read_text())
        self.assertFalse(inst.autostart_entry().exists())
        self.assertEqual(len(inst.load_manifest(self.dir)["shortcuts"]), 3)

    def test_windows_update_moves_start_menu_to_the_renamed_launcher(self):
        appdata = Path(self.tmp.name) / "Roaming"
        with mock.patch.object(inst, "IS_WINDOWS", True), \
                mock.patch.dict(os.environ, {"APPDATA": str(appdata)}):
            # A 0.2.4 install: its settings launcher, and Start menu entries that call it.
            old = self.dir / "ft-assistant-setup.cmd"
            old.write_text('@echo off\r\ncd /d "x"\r\nstart "" "pythonw.exe" -m ft_assistant.open_setup\r\n')
            inst.save_manifest(self.dir, {"gpu": True, "model": "m"})
            menu = inst.menu_dir()
            menu.mkdir(parents=True)
            (menu / "FT Assistant setup.cmd").write_text(f'@call "{old}"\r\n')
            inst.autostart_dir().mkdir(parents=True)
            inst.autostart_entry().write_text("@call x\r\n")
            with mock.patch.object(inst, "install_packages"), mock.patch.object(inst, "start_app"), \
                    mock.patch.object(inst, "register_windows_app"):
                inst.main(["finish-update", "--dir", str(self.dir)])
            self.assertFalse(old.exists())
            new = self.dir / "ft-assistant-settings.cmd"
            self.assertIn("-m ft_assistant.open_setup", new.read_text())
            self.assertIn(str(new), (menu / "FT Assistant setup.cmd").read_text())
            self.assertTrue(inst.autostart_entry().exists())        # login entry kept
            self.assertEqual(len(inst.load_manifest(self.dir)["shortcuts"]), 4)

    def test_launchers_and_shortcuts(self):
        launchers = inst.write_launchers(self.dir, gpu=True, model="large-v3-turbo")
        text = launchers["ft-assistant"].read_text()
        self.assertIn(f'FT_ASSISTANT_DATA_DIR="{self.dir}"', text)
        self.assertIn('FT_ASSISTANT_DEVICE="cuda"', text)
        self.assertIn("LD_LIBRARY_PATH", text)
        self.assertIn("-m ft_assistant", text)
        self.assertIn(f'cd "{self.dir}"', text)        # never runs code from the caller's folder
        self.assertTrue(os.access(launchers["ft-assistant"], os.X_OK))
        cpu = inst.write_launchers(self.dir, gpu=False, model="small.en")["ft-assistant"].read_text()
        self.assertIn('FT_ASSISTANT_DEVICE="cpu"', cpu)
        self.assertNotIn("LD_LIBRARY_PATH", cpu)
        shortcuts = inst.write_shortcuts(launchers, autostart=True)
        names = sorted(p.name for p in shortcuts)
        self.assertEqual(names, ["ft-assistant-setup.desktop", "ft-assistant-uninstall.desktop",
                                 "ft-assistant.desktop", "ft-assistant.desktop"])
        self.assertIn(str(launchers["ft-assistant-settings"]),
                      (Path(self.tmp.name) / "data" / "applications" / "ft-assistant-setup.desktop")
                      .read_text())
        self.assertTrue(all(str(p).startswith(self.tmp.name) for p in shortcuts))
        self.assertEqual(len(inst.write_shortcuts(launchers, autostart=False)), 3)

    def test_system_gpu_libs_skip_library_path_and_repair_notice(self):
        text = inst.write_launchers(self.dir, gpu=True, model="large-v3-turbo",
                                    gpu_libs="system")["ft-assistant"].read_text()
        self.assertIn('FT_ASSISTANT_DEVICE="cuda"', text)
        self.assertNotIn("LD_LIBRARY_PATH", text)
        self.assertIn("needs a repair", text)            # shown if a system upgrade broke Python
        self.assertIn('PYTHONNOUSERSITE="1"', text)

    def make_cached_model(self, root, name="large-v3-turbo", shared_store=False):
        """A Hugging Face style cache entry: snapshot files are links into blobs/ (or, in newer
        caches, into a cache-wide shared store)."""
        repo = Path(root) / f"models--mobiuslabsgmbh--faster-whisper-{name}"
        snap = repo / "snapshots" / "123"
        snap.mkdir(parents=True)
        (repo / "blobs").mkdir()
        for f in ("model.bin", "config.json", "tokenizer.json"):
            if shared_store:
                (Path(root) / "blobs" / "b5").mkdir(parents=True, exist_ok=True)
                (Path(root) / "blobs" / "b5" / f).write_bytes(b"data " + f.encode())
                os.symlink(f"../../blobs/b5/{f}", repo / "blobs" / f)
            else:
                (repo / "blobs" / f).write_bytes(b"data " + f.encode())
            os.symlink(f"../../blobs/{f}", snap / f)
        return snap

    def test_find_model(self):
        cache = Path(self.tmp.name, "hfcache")
        self.assertIsNone(inst.find_model("large-v3-turbo", [cache]))
        snap = self.make_cached_model(cache)
        self.assertEqual(inst.find_model("large-v3-turbo", [cache]), snap)
        self.assertIsNone(inst.find_model("small.en", [cache]))

    def test_model_reused_as_plain_hard_linked_files(self):
        for shared in (False, True):
            with self.subTest(shared_store=shared):
                cache = Path(self.tmp.name, f"hfcache{shared}")
                snap = self.make_cached_model(cache, shared_store=shared)
                d = self.dir / f"i{shared}"
                with mock.patch.dict(os.environ, {"FT_ASSISTANT_MODEL_SOURCE": str(cache)}):
                    target = inst.install_model(d, gpu=True)
                self.assertEqual(target, d / "models" / "large-v3-turbo")
                ours = target / "model.bin"
                self.assertFalse(ours.is_symlink())                       # plain file
                self.assertTrue(os.path.samefile(ours, (snap / "model.bin").resolve()))
                (snap / "model.bin").resolve().unlink()                   # original deleted:
                self.assertEqual(ours.read_bytes(), b"data model.bin")    # ours still works
                self.assertEqual(inst.install_model(d, gpu=True), target)  # already there

    def test_broken_model_not_found(self):
        cache = Path(self.tmp.name, "hfcache")
        snap = cache / "models--x--faster-whisper-small.en" / "snapshots" / "1"
        snap.mkdir(parents=True)
        for f in ("model.bin", "config.json", "tokenizer.json"):
            os.symlink("../../blobs/missing", snap / f)
        self.assertIsNone(inst.find_model("small.en", [cache]))
        # Empty placeholder files (what Wine leaves for links) don't count either.
        for f in ("model.bin", "config.json", "tokenizer.json"):
            (snap / f).unlink()
            (snap / f).write_bytes(b"")
        self.assertIsNone(inst.find_model("small.en", [cache]))

    def test_packages_failure_exit_code(self):
        with mock.patch.object(inst, "install_packages", side_effect=inst.PackagesFailed("no wheel")), \
                mock.patch.object(inst, "stop_running_app"):
            with self.assertRaises(SystemExit) as cm:
                inst.main(["install", "--dir", str(self.dir), "--gpu", "no", "--no-start"])
        self.assertEqual(cm.exception.code, 3)

    def test_system_python_without_windows_falls_back(self):
        # e.g. python.org Python installed without "tcl/tk": setup must switch to a downloaded
        # Python (exit code 3) before downloading anything, not install a broken setup screen.
        with mock.patch.object(inst, "can_draw_windows", return_value=False), \
                mock.patch.object(inst, "install_packages") as pkgs, \
                mock.patch.object(inst, "stop_running_app"):
            with self.assertRaises(SystemExit) as cm:
                inst.main(["install", "--dir", str(self.dir), "--gpu", "no", "--no-start",
                           "--python-source", "system"])
        self.assertEqual(cm.exception.code, 3)
        pkgs.assert_not_called()

    def test_window_test_runs_the_given_python(self):
        ok = mock.Mock(returncode=0)
        with mock.patch.object(inst.subprocess, "run", return_value=ok) as run:
            self.assertTrue(inst.can_draw_windows("/x/python"))
        argv = run.call_args[0][0]
        self.assertEqual(argv[0], "/x/python")
        self.assertIn("tkinter.Tk()", argv[2])
        with mock.patch.object(inst.subprocess, "run", return_value=mock.Mock(returncode=1)):
            self.assertFalse(inst.can_draw_windows("/x/python"))
        self.assertFalse(inst.can_draw_windows(self.dir / "no-such-python"))

    def _lock(self, pid):
        d = Path(os.environ["XDG_CONFIG_HOME"]) / "ft-assistant"
        d.mkdir(parents=True, exist_ok=True)
        (d / ".lock").write_text(str(pid))

    def test_stale_lock_never_stops_another_program(self):
        # The lock still holds the id of an FT Assistant that has since exited, now reused by
        # some other program: it must be left alone.
        other = subprocess.Popen(["sleep", "30"])
        try:
            self._lock(other.pid)
            inst.stop_running_app()
            self.assertIsNone(other.poll())
        finally:
            other.kill(); other.wait()

    def test_running_app_is_stopped(self):
        self._lock(4242)
        with mock.patch.object(inst, "is_ft_assistant", return_value=True), \
                mock.patch.object(inst.os, "kill") as kill, mock.patch.object(inst.time, "sleep"):
            inst.stop_running_app()
        kill.assert_called_once_with(4242, 15)

    def test_app_recognised_by_command_line(self):
        self.assertTrue(inst.APP_CMDLINE_RE.search("/x/python3 -m ft_assistant"))
        self.assertTrue(inst.APP_CMDLINE_RE.search('"C:\\x\\pythonw.exe" -m ft_assistant '))
        self.assertFalse(inst.APP_CMDLINE_RE.search("/x/python3 -m ft_assistant.setup_ui"))
        self.assertFalse(inst.APP_CMDLINE_RE.search("sleep 30"))

    def test_uninstall_removes_everything_it_made(self):
        launchers = inst.write_launchers(self.dir, gpu=False, model="small.en")
        shortcuts = inst.write_shortcuts(launchers)
        inst.write_vocabulary()
        inst.save_manifest(self.dir, {"shortcuts": [str(p) for p in shortcuts]})
        inst.main(["uninstall", "--dir", str(self.dir), "--yes"])
        self.assertFalse(self.dir.exists())
        self.assertFalse(any(p.exists() for p in shortcuts))
        self.assertFalse(inst.config_dir().exists())

    def test_uninstall_keep_settings(self):
        inst.write_vocabulary()
        inst.save_manifest(self.dir, {"shortcuts": []})
        inst.main(["uninstall", "--dir", str(self.dir), "--yes", "--keep-settings"])
        self.assertTrue((inst.config_dir() / "vocabulary.txt").exists())

    def test_uninstall_refuses_unknown_folder(self):
        with self.assertRaises(SystemExit):
            inst.main(["uninstall", "--dir", str(self.dir), "--yes"])
        self.assertTrue(self.dir.exists())


class SetupFile(unittest.TestCase):
    def _linux_gpu_check(self, smi_output):
        """Run the Linux part's graphics-card check with a pretend nvidia-smi."""
        text = (REPO / "installer" / "setup-template.cmd").read_text(encoding="utf-8")
        start = text.index("\nGPU=no\n") + 1
        snippet = text[start:text.index('case "${FT_SETUP_GPU:-}"', start)]
        with tempfile.TemporaryDirectory() as t:
            # Only these tools on the search path, so this computer's own nvidia-smi isn't used.
            for tool in ("sh", "grep", "sed", "head", "cat"):
                os.symlink(subprocess.run(["bash", "-c", f"command -v {tool}"], capture_output=True,
                                          text=True).stdout.strip(), Path(t, tool))
            if smi_output is not None:
                smi = Path(t, "nvidia-smi")
                smi.write_text("#!/bin/sh\n[ \"$1\" = -L ] && echo 'GPU 0: NVIDIA GeForce GTX 770' "
                               f"&& exit 0\ncat <<'X'\n{smi_output}\nX\n")
                smi.chmod(0o755)
            script = "say() { printf '%s\\n' \"$*\"; }\n" + snippet + 'echo "GPU=$GPU"\n'
            r = subprocess.run([shutil.which("bash"), "-c", script], capture_output=True,
                               text=True, env={"PATH": t})
        return r.stdout

    def test_old_nvidia_driver_uses_the_processor(self):
        out = self._linux_gpu_check("| NVIDIA-SMI 470.256.02   Driver Version: 470.256.02   "
                                    "CUDA Version: 11.4     |")
        self.assertIn("GPU=no", out)
        self.assertIn("driver is too old", out)

    def test_current_nvidia_driver_uses_the_card(self):
        out = self._linux_gpu_check("| NVIDIA-SMI 580.95   Driver Version: 580.95   "
                                    "CUDA Version: 13.2     |")
        self.assertEqual(out.strip(), "GPU=yes")
        self.assertEqual(self._linux_gpu_check(None).strip(), "GPU=no")

    def test_windows_checks_the_nvidia_driver(self):
        text = (REPO / "installer" / "setup-template.cmd").read_text(encoding="utf-8")
        self.assertIn("function Get-CudaMajor", text)
        self.assertIn("$cudaMajor -lt 12", text)

    def test_never_uses_the_computers_python(self):
        text = (REPO / "installer" / "setup-template.cmd").read_text(encoding="utf-8")
        for gone in ("python3 -m venv", "-m venv", "Find-SystemPython", "python3-venv",
                     "python3-tk", "releases/latest"):
            self.assertNotIn(gone, text)
        self.assertIn("function Test-OwnPython", text)            # Windows: reuse
        self.assertIn("Get-FileHash -Algorithm SHA256", text)     # Windows: checked download

    def built(self, t):
        spec_b = importlib.util.spec_from_file_location("ft_build", REPO / "installer" / "build.py")
        build = importlib.util.module_from_spec(spec_b)
        spec_b.loader.exec_module(build)
        return build.build(Path(t, "FT-Assistant-setup.cmd"))

    def linux_functions(self, out):
        text = out.read_text()
        start = text.index("# FT Assistant's own Python (pinned")
        return text[start:text.index("\nGPU_LIBS=", start)] + "\n"

    def test_linux_part_reads_the_pinned_python(self):
        with tempfile.TemporaryDirectory() as t:
            out = self.built(t)
            script = ("fail() { echo FAIL; exit 1; }\n" + f"SELF='{out}'\n" + self.linux_functions(out)
                      + 'echo "$RUNTIME_ID $RUNTIME_SHA256 $RUNTIME_MARKER"\n')
            r = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
        self.assertEqual(r.stdout.split(), [inst.RUNTIME_ID, inst.RUNTIME_SHA256_LINUX,
                                            inst.RUNTIME_MARKER])

    def test_linux_part_reuses_its_own_python_only(self):
        with tempfile.TemporaryDirectory() as t:
            out = self.built(t)
            d = Path(t, "install")
            py = d / "python" / "bin" / "python3"
            py.parent.mkdir(parents=True)
            py.write_text(f"#!/bin/sh\necho {inst.RUNTIME_PYTHON}\n")
            py.chmod(0o755)
            check = ("fail() { echo FAIL; exit 1; }\n" + f"SELF='{out}'\n" + self.linux_functions(out)
                     + f"runtime_ok '{d}' && echo reuse || echo download\n")
            run = lambda: subprocess.run(["bash", "-c", check], capture_output=True,  # noqa: E731
                                         text=True).stdout.strip()
            self.assertEqual(run(), "download")                      # no marker: not ours
            (d / "python" / inst.RUNTIME_MARKER).write_text(inst.RUNTIME_ID + "\n")
            self.assertEqual(run(), "reuse")
            (d / "python" / "pyvenv.cfg").write_text("home = /usr/bin\n")
            self.assertEqual(run(), "download")                      # a venv of the system Python
            (d / "python" / "pyvenv.cfg").unlink()
            (d / "python" / inst.RUNTIME_MARKER).write_text("cpython-3.12.1+20240101\n")
            self.assertEqual(run(), "download")                      # an older runtime

    def test_built_file(self):
        with tempfile.TemporaryDirectory() as t:
            out = self.built(t)
            text = out.read_text()
            self.assertTrue(text.startswith(':<<"::CMDLITERAL"\n@echo off'))
            self.assertLess(out.stat().st_size, 100_000)
            # The Linux part is valid bash.
            linux = text[text.index("::CMDLITERAL\n# ----"):text.index("#__FT_ASSISTANT_PS__")]
            r = subprocess.run(["bash", "-n"], input=linux, text=True, capture_output=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            # The installer embedded at the end is extracted exactly by the Linux part's sed.
            r = subprocess.run(["bash", "-c", f"sed -n '/^#__FT_ASSISTANT_INSTALLER__$/,$p' '{out}' "
                                              "| tail -n +2"], capture_output=True, text=True)
            self.assertEqual(r.stdout, (REPO / "installer" / "install.py").read_text())


if __name__ == "__main__":
    unittest.main()
