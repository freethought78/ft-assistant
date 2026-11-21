"""FT Assistant's own Python: reuse, moving existing installs over, smooth text on Linux."""
import importlib.util
import io
import os
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("ft_install_rt", REPO / "installer" / "install.py")
inst = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inst)


def fake_python(pydir, version=None):
    """A runtime folder whose bin/python3 just prints a version."""
    py = Path(pydir) / "bin" / "python3"
    py.parent.mkdir(parents=True, exist_ok=True)
    py.write_text(f"#!/bin/sh\necho {version or inst.RUNTIME_PYTHON}\n")
    py.chmod(0o755)
    return py


@unittest.skipIf(sys.platform == "win32", "uses shell scripts as pretend Pythons")
class Runtime(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.t = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_only_the_pinned_own_runtime_counts(self):
        pydir = self.t / "python"
        fake_python(pydir)
        self.assertFalse(inst.runtime_ok(pydir))                          # no marker
        (pydir / inst.RUNTIME_MARKER).write_text(inst.RUNTIME_ID + "\n")
        self.assertTrue(inst.runtime_ok(pydir))
        (pydir / "pyvenv.cfg").write_text("home = /usr/bin\n")
        self.assertFalse(inst.runtime_ok(pydir))                          # a venv
        (pydir / "pyvenv.cfg").unlink()
        fake_python(pydir, "3.12.1")
        self.assertFalse(inst.runtime_ok(pydir))                          # doesn't match

    def test_fetch_runtime_unpacks_and_marks_it(self):
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as tar:
            data = b"#!/bin/sh\necho hi\n"
            info = tarfile.TarInfo("python/bin/python3")
            info.size, info.mode = len(data), 0o755
            tar.addfile(info, io.BytesIO(data))
        archive = self.t / "py.tar.gz"
        archive.write_bytes(buf.getvalue())
        with mock.patch.dict(os.environ, {"FT_SETUP_PYTHON_TARBALL": str(archive)}):
            inst.fetch_runtime(self.t / "python.new")
        self.assertTrue((self.t / "python.new" / "bin" / "python3").exists())
        self.assertEqual(inst.runtime_id(self.t / "python.new"), inst.RUNTIME_ID)
        self.assertEqual(sorted(p.name for p in self.t.iterdir()),
                         ["py.tar.gz", "python.new"])           # no temporary folders left


@unittest.skipIf(sys.platform == "win32", "Linux only")
class SmoothText(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.pydir = Path(self.tmp.name, "python")
        (self.pydir / "lib").mkdir(parents=True)
        self.lib = self.pydir / "lib" / "libtcl9tk9.0.so"
        self.lib.write_bytes(b"rough tk")
        self.smooth = Path(self.tmp.name, "smooth.so")
        self.smooth.write_bytes(b"smooth tk")
        self.env = mock.patch.dict(os.environ, {"FT_SETUP_SMOOTH_TK": str(self.smooth)})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def run_with(self, answers):
        with mock.patch.object(inst, "tk_info", side_effect=answers):
            return inst.ensure_smooth_tk(self.pydir)

    def test_swaps_in_the_smooth_tk(self):
        self.assertEqual(self.run_with([("9.0.4", "x11"), ("9.0.4", "xft")]), "smooth")
        self.assertEqual(self.lib.read_bytes(), b"smooth tk")
        self.assertEqual(Path(str(self.lib) + ".rough").read_bytes(), b"rough tk")

    def test_puts_the_original_back_when_it_doesnt_work_here(self):
        self.assertEqual(self.run_with([("9.0.4", "x11"), None]), "rough")
        self.assertEqual(self.lib.read_bytes(), b"rough tk")           # window still opens

    def test_leaves_other_tk_versions_alone(self):
        self.assertEqual(self.run_with([("8.6.15", "x11")]), "rough")
        self.assertEqual(self.lib.read_bytes(), b"rough tk")

    def test_already_smooth(self):
        self.assertEqual(self.run_with([("9.0.4", "xft")]), "smooth")
        self.assertFalse(Path(str(self.lib) + ".rough").exists())


class MovingOver(unittest.TestCase):
    """An update moves an install made from the computer's Python onto FT Assistant's own."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = Path(self.tmp.name)
        self.d = t / "install"
        (self.d / "python").mkdir(parents=True)
        (self.d / "python" / "pyvenv.cfg").write_text("home = /usr/bin\n")     # a venv
        (self.d / "app" / "ft_assistant").mkdir(parents=True)
        (self.d / "app.previous" / "ft_assistant").mkdir(parents=True)
        inst.save_manifest(self.d, {"gpu": True, "model": "m", "gpu_libs": "pip",
                                    "python": "system"})
        self.env = mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": str(t / "config"),
                                                "XDG_DATA_HOME": str(t / "data"),
                                                "APPDATA": str(t / "Roaming")})
        self.env.start()
        self.packages = []

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def fake_fetch(self, pydir):
        (Path(pydir) / "bin").mkdir(parents=True)
        (Path(pydir) / inst.RUNTIME_MARKER).write_text(inst.RUNTIME_ID)

    def patches(self, **extra):
        return [mock.patch.object(inst, "fetch_runtime", side_effect=self.fake_fetch),
                mock.patch.object(inst, "ensure_smooth_tk", return_value="smooth"),
                mock.patch.object(inst, "install_packages",
                                  side_effect=lambda d, gpu, libs, py=None: self.packages.append(py)),
                mock.patch.object(inst, "start_app"),
                mock.patch.object(inst, "register_windows_app"),
                mock.patch.object(inst, "wait_ready", return_value=True)] + \
            [mock.patch.object(inst, k, v) for k, v in extra.items()]

    def run_update(self, **extra):
        ps = self.patches(**extra)
        for p in ps:
            p.start()
        try:
            inst.main(["finish-update", "--dir", str(self.d)])
        finally:
            for p in reversed(ps):
                p.stop()

    @unittest.skipIf(sys.platform == "win32", "the Linux way")
    def test_linux_swaps_in_the_new_python_and_drops_the_old_once_started(self):
        self.run_update()
        self.assertEqual(inst.runtime_id(self.d / "python"), inst.RUNTIME_ID)
        self.assertFalse((self.d / "python" / "pyvenv.cfg").exists())
        self.assertFalse((self.d / "python.old").exists())           # removed after the start
        self.assertFalse((self.d / "python.new").exists())
        self.assertEqual(self.packages, [inst.runtime_python(self.d / "python.new")])
        info = inst.load_manifest(self.d)
        self.assertEqual((info["python"], info["runtime"]), ("standalone", inst.RUNTIME_ID))

    @unittest.skipIf(sys.platform == "win32", "the Linux way")
    def test_old_python_kept_if_the_app_doesnt_start(self):
        self.run_update(wait_ready=mock.Mock(return_value=False))
        self.assertTrue((self.d / "python.old" / "pyvenv.cfg").exists())

    def test_failure_keeps_everything_as_it_was(self):
        def broken(pydir):
            Path(pydir).mkdir()
            raise RuntimeError("no internet")
        with self.assertRaises(SystemExit):
            self.run_update(fetch_runtime=mock.Mock(side_effect=broken))
        self.assertTrue((self.d / "python" / "pyvenv.cfg").exists())  # old Python untouched
        self.assertFalse((self.d / "python.new").exists())
        self.assertEqual(inst.load_manifest(self.d)["python"], "system")

    def test_windows_hands_over_to_a_helper_and_doesnt_wait_for_enter(self):
        popen = mock.Mock()
        with mock.patch("builtins.input", side_effect=AssertionError("waited for Enter")):
            with self.assertRaises(SystemExit) as cm:
                ps = self.patches(IS_WINDOWS=True)
                for p in ps:
                    p.start()
                try:
                    with mock.patch.object(inst.subprocess, "Popen", popen):
                        inst.main(["finish-update", "--dir", str(self.d), "--pause"])
                finally:
                    for p in reversed(ps):
                        p.stop()
        self.assertEqual(cm.exception.code, inst.HANDED_OVER)
        helper = (self.d / "finish-update.cmd").read_text()
        self.assertIn('move "python" "python.old"', helper)
        self.assertIn('move "python.new" "python"', helper)
        self.assertIn("finish-runtime", helper)
        self.assertTrue((self.d / "python.new").exists())             # swapped by the helper
        self.assertEqual(popen.call_args[0][0][:2], ["cmd", "/c"])


if __name__ == "__main__":
    unittest.main()
