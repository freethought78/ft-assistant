"""FT Assistant's processes are called "FT Assistant", not python/pythonw."""
import importlib.util
import os
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ft_assistant import procname

REPO = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("ft_install_pn", REPO / "installer" / "install.py")
inst = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inst)


def read_strings(data):
    """The StringFileInfo strings of a VS_VERSIONINFO (a small reader for the test)."""
    out = {}

    def walk(off, end):
        while off < end:
            length, vlen, typ = struct.unpack_from("<HHH", data, off)
            if length == 0:
                break
            k_end = data.index(b"\0\0", off + 6)
            while (k_end - (off + 6)) % 2:
                k_end = data.index(b"\0\0", k_end + 1)
            key = data[off + 6:k_end].decode("utf-16-le")
            v = k_end + 2
            v += -v % 4
            if typ == 1 and vlen:
                out[key] = data[v:v + vlen * 2].decode("utf-16-le").rstrip("\0")
                v += vlen * 2
            else:
                v += vlen
            v += -v % 4
            walk(v, off + length)
            off += length
            off += -off % 4

    walk(0, len(data))
    return out


class Names(unittest.TestCase):
    def test_names_match_between_app_and_installer(self):
        self.assertEqual(procname.WINDOWS_EXES, inst.NAMED_PROGRAMS)
        for name in procname.LINUX_NAMES.values():
            self.assertLessEqual(len(name.encode()), 15)          # the Linux limit

    @unittest.skipUnless(sys.platform.startswith("linux"), "Linux only")
    def test_linux_process_takes_the_name(self):
        r = subprocess.run([sys.executable, "-c",
                            "import procname; procname.set_name('app'); "
                            "print(open('/proc/self/comm').read().strip())"],
                           capture_output=True, text=True, cwd=REPO / "ft_assistant")
        self.assertEqual(r.stdout.strip(), "FT Assistant")

    def test_windows_starts_the_named_copy_when_it_exists(self):
        with tempfile.TemporaryDirectory() as t:
            py = Path(t, "pythonw.exe")
            py.write_text("x")
            self.assertEqual(procname.executable("speech", py, windows=True), str(py))
            Path(t, "FT Assistant speech.exe").write_text("x")
            self.assertEqual(procname.executable("speech", py, windows=True),
                             str(Path(t, "FT Assistant speech.exe")))
            self.assertEqual(procname.executable("speech", py, windows=False), str(py))


class WindowsCopies(unittest.TestCase):
    def test_version_resource_says_ft_assistant(self):
        data = inst.version_info("FT Assistant", "3.12.16")
        self.assertEqual(struct.unpack_from("<H", data, 0)[0], len(data))
        s = read_strings(data)
        self.assertEqual(s["FileDescription"], "FT Assistant")
        self.assertEqual(s["ProductName"], "FT Assistant")
        self.assertEqual(s["FileVersion"], "3.12.16")

    def test_named_copies_and_the_launcher_uses_them(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            (d / "python").mkdir()
            (d / "python" / "python.exe").write_text("py")
            (d / "python" / "pythonw.exe").write_text("pyw")
            with mock.patch.object(inst, "IS_WINDOWS", True), \
                    mock.patch.object(inst, "set_description") as describe:
                self.assertEqual(inst.pythonw_exe(d).name, "pythonw.exe")
                inst.make_named_programs(d / "python")
                self.assertEqual(inst.pythonw_exe(d).name, "FT Assistant.exe")
            for name in inst.NAMED_PROGRAMS.values():
                self.assertEqual((d / "python" / name).read_text(), "pyw")
            self.assertEqual(describe.call_count, 4)
            self.assertFalse(list((d / "python").glob("*.new")))


if __name__ == "__main__":
    unittest.main()
