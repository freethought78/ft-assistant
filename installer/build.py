#!/usr/bin/env python3
"""Build dist/FT-Assistant-Installer.cmd: the setup template with installer/install.py appended.

    python3 installer/build.py

Also writes a copy under the installer's old name (LEGACY_NAMES), to attach to a release or two
so links to releases/latest/download/FT-Assistant-setup.cmd keep working. Drop it after that."""

from pathlib import Path

HERE = Path(__file__).resolve().parent
MARK = "#__FT_ASSISTANT_INSTALLER__"
NAME = "FT-Assistant-Installer.cmd"
LEGACY_NAMES = ("FT-Assistant-setup.cmd",)      # the name until 0.2.8


def build(out=None):
    template = (HERE / "setup-template.cmd").read_text(encoding="utf-8")
    assert template.rstrip("\n").endswith(MARK), "template must end with the installer marker"
    installer = (HERE / "install.py").read_text(encoding="utf-8")
    default = out is None
    out = Path(out or HERE.parent / "dist" / NAME)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(template.rstrip("\n") + "\n" + installer, encoding="utf-8", newline="\n")
    if default:
        for old in LEGACY_NAMES:
            (out.parent / old).write_bytes(out.read_bytes())
    return out


if __name__ == "__main__":
    p = build()
    print(f"{p} ({p.stat().st_size // 1024} KB), and the same under its old name: "
          + ", ".join(LEGACY_NAMES))
