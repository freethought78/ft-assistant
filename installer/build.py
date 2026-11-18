#!/usr/bin/env python3
"""Build dist/FT-Assistant-setup.cmd: the setup template with installer/install.py appended.

    python3 installer/build.py"""

from pathlib import Path

HERE = Path(__file__).resolve().parent
MARK = "#__FT_ASSISTANT_INSTALLER__"


def build(out=None):
    template = (HERE / "setup-template.cmd").read_text(encoding="utf-8")
    assert template.rstrip("\n").endswith(MARK), "template must end with the installer marker"
    installer = (HERE / "install.py").read_text(encoding="utf-8")
    out = Path(out or HERE.parent / "dist" / "FT-Assistant-setup.cmd")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(template.rstrip("\n") + "\n" + installer, encoding="utf-8", newline="\n")
    return out


if __name__ == "__main__":
    p = build()
    print(f"{p} ({p.stat().st_size // 1024} KB)")
