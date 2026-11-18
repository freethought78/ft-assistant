import importlib.util
import io
import os
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

    def tearDown(self):
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

    def test_launchers_and_shortcuts(self):
        launchers = inst.write_launchers(self.dir, gpu=True, model="large-v3-turbo")
        text = launchers["ft-assistant"].read_text()
        self.assertIn(f'FT_ASSISTANT_DATA_DIR="{self.dir}"', text)
        self.assertIn('FT_ASSISTANT_DEVICE="cuda"', text)
        self.assertIn("LD_LIBRARY_PATH", text)
        self.assertIn("-m ft_assistant", text)
        self.assertTrue(os.access(launchers["ft-assistant"], os.X_OK))
        cpu = inst.write_launchers(self.dir, gpu=False, model="small.en")["ft-assistant"].read_text()
        self.assertIn('FT_ASSISTANT_DEVICE="cpu"', cpu)
        self.assertNotIn("LD_LIBRARY_PATH", cpu)
        shortcuts = inst.write_shortcuts(launchers, autostart=True)
        names = sorted(p.name for p in shortcuts)
        self.assertEqual(names, ["ft-assistant-setup.desktop", "ft-assistant-uninstall.desktop",
                                 "ft-assistant.desktop", "ft-assistant.desktop"])
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
    def test_built_file(self):
        spec_b = importlib.util.spec_from_file_location("ft_build", REPO / "installer" / "build.py")
        build = importlib.util.module_from_spec(spec_b)
        spec_b.loader.exec_module(build)
        with tempfile.TemporaryDirectory() as t:
            out = build.build(Path(t, "FT-Assistant-setup.cmd"))
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
