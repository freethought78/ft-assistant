"""FT Assistant installer, updater and uninstaller (shared by Linux and Windows).

The setup script (FT-Assistant-setup.cmd) has already checked requirements, shown the
download size, asked for the install folder and downloaded a standalone Python into
<install dir>/python. It then runs this file with that Python:

    python install.py install   --dir DIR --gpu yes|no [--gpu-libs pip|system]
                                [--source PATH_OR_URL] [--no-autostart]
    python install.py update    --dir DIR [--source PATH_OR_URL]
    python install.py uninstall --dir DIR [--keep-settings] [--yes]

Only the standard library is used here. Everything is per-user; no admin rights needed.

Reuse before download: <install dir>/python may be a venv made from the computer's own Python
(the setup script prefers that) or a downloaded standalone Python; NVIDIA libraries already
installed system-wide are used instead of pip copies (--gpu-libs system); a Whisper model that
is already on the computer (shared Hugging Face cache, or the earlier voice-dictation tool) is
hard-linked instead of downloaded, so it takes no extra disk space.

Testing hooks (environment):
  FT_ASSISTANT_SOURCE        local folder or zip with the app code (instead of GitHub)
  FT_ASSISTANT_MODEL_SOURCE  local folder to copy the Whisper model from (instead of downloading)
  XDG_CONFIG_HOME / XDG_DATA_HOME  where settings and menu/login entries go (Linux)"""

import argparse
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile
from pathlib import Path

APP_NAME = "FT Assistant"
GITHUB_REPO = "freethought78/ft-assistant"
IS_WINDOWS = sys.platform == "win32"

GPU_MODEL = "large-v3-turbo"
CPU_MODEL = "small.en"

COMMON_PACKAGES = ["faster-whisper==1.2.1", "ctranslate2==4.9.0", "numpy", "sounddevice==0.5.6"]
LINUX_PACKAGES = ["python-xlib==0.33"]
WINDOWS_PACKAGES = []                       # the Windows layer uses ctypes only
# 12.9.3.13 has no Windows build; 12.9.2.10 is the newest cuBLAS built for both systems.
GPU_PACKAGES = ["nvidia-cublas-cu12==" + ("12.9.2.10" if IS_WINDOWS else "12.9.3.13"),
                "nvidia-cudnn-cu12==9.28.1.4"]


def say(msg=""):
    print(msg, flush=True)


TOTAL_STEPS = 6          # steps 1-2 happen in the setup script (requirements, Python)


def step(n, text, total=TOTAL_STEPS):
    """A clear step header, so the user always knows what's happening and that it's moving."""
    say("")
    say(f"Step {n} of {total}: {text}")


# ---------------------------------------------------------------- locations

def home():
    return Path.home()


def config_dir():
    if IS_WINDOWS:
        return Path(os.environ.get("APPDATA", home() / "AppData" / "Roaming")) / APP_NAME
    return Path(os.environ.get("XDG_CONFIG_HOME") or home() / ".config") / "ft-assistant"


def autostart_dir():
    if IS_WINDOWS:
        return Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
    return Path(os.environ.get("XDG_CONFIG_HOME") or home() / ".config") / "autostart"


def menu_dir():
    if IS_WINDOWS:
        return Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / APP_NAME
    return Path(os.environ.get("XDG_DATA_HOME") or home() / ".local" / "share") / "applications"


def python_exe(install_dir):
    if IS_WINDOWS:
        venv = Path(install_dir) / "python" / "Scripts" / "python.exe"
        return venv if venv.exists() else Path(install_dir) / "python" / "python.exe"
    return Path(install_dir) / "python" / "bin" / "python3"


def pythonw_exe(install_dir):
    """Windows: the no-console Python next to python_exe()."""
    return python_exe(install_dir).with_name("pythonw.exe")


class PackagesFailed(RuntimeError):
    """pip couldn't install the packages (e.g. no ready-made build for this Python version)."""


# ---------------------------------------------------------------- steps

def run(cmd, **kw):
    say("  $ " + " ".join(str(c) for c in cmd))
    env = dict(os.environ, PYTHONNOUSERSITE="1",    # never mix in the user's own Python packages
               HF_HUB_DISABLE_XET="1",                # plain per-file progress bars for the model
               HF_HUB_VERBOSITY="error")              # no "unauthenticated requests" warning
    subprocess.run([str(c) for c in cmd], check=True, env=env, **kw)


def install_packages(install_dir, gpu, gpu_libs="pip"):
    """pip keeps its download cache in the user's shared pip cache, so packages already
    downloaded for any other project are reused instead of downloaded again."""
    py = python_exe(install_dir)
    pkgs = COMMON_PACKAGES + (WINDOWS_PACKAGES if IS_WINDOWS else LINUX_PACKAGES)
    pip_gpu = gpu and gpu_libs == "pip"
    if pip_gpu:
        pkgs += GPU_PACKAGES
    if pip_gpu:
        say("  The speech engine and NVIDIA GPU libraries: about 1.5 GB to download, so this can")
        say("  take several minutes. Progress bars below show each download.")
    else:
        say("  About 150 MB to download; this usually takes a minute or two. Progress bars below.")
    if gpu and not pip_gpu:
        say("  (using the NVIDIA libraries already installed on this computer)")
    try:
        run([py, "-m", "pip", "install", "--disable-pip-version-check",
             "--no-warn-script-location", "--upgrade"] + pkgs)
    except subprocess.CalledProcessError as e:
        raise PackagesFailed(str(e)) from e


def _latest_release_zip():
    url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
    req = urllib.request.Request(url, headers={"User-Agent": "FT-Assistant-installer",
                                               "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read().decode())
    return data["zipball_url"], data.get("tag_name", "")


def fetch_app(install_dir, source=None):
    """Put the ft_assistant package into <dir>/app/ft_assistant. Returns the source label.

    The release's own installer (installer/install.py) is saved next to it as install.py.new,
    so an update can hand over to the newer installer."""
    source = source or os.environ.get("FT_ASSISTANT_SOURCE")
    app = Path(install_dir) / "app"
    new = Path(install_dir) / "app.new"
    shutil.rmtree(new, ignore_errors=True)
    new.mkdir(parents=True)
    if source and Path(source).is_dir():
        src = Path(source)
        pkg = src / "ft_assistant" if (src / "ft_assistant").is_dir() else src
        shutil.copytree(pkg, new / "ft_assistant",
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        if (src / "installer" / "install.py").is_file():
            shutil.copyfile(src / "installer" / "install.py", Path(install_dir) / "install.py.new")
        label = str(src)
    else:
        if source and (source.startswith("http") or Path(source).is_file()):
            url, label = source, source
        else:
            url, label = _latest_release_zip()
        say("  Downloading FT Assistant...")
        if url.startswith("http"):
            req = urllib.request.Request(url, headers={"User-Agent": "FT-Assistant-installer"})
            with urllib.request.urlopen(req, timeout=60) as r:
                blob = r.read()
        else:
            blob = Path(url).read_bytes()
        with zipfile.ZipFile(io.BytesIO(blob)) as z:
            names = [n for n in z.namelist() if "/ft_assistant/" in "/" + n and not n.endswith("/")]
            if not names:
                raise RuntimeError("the download doesn't contain the FT Assistant program")
            for n in names:
                rel = n[("/" + n).index("/ft_assistant/"):]   # strip the archive's top folder
                dest = new / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(z.read(n))
            inst = [n for n in z.namelist() if ("/" + n).endswith("/installer/install.py")]
            if inst:
                (Path(install_dir) / "install.py.new").write_bytes(z.read(inst[0]))
    # swap in, keeping the previous version for rollback
    prev = Path(install_dir) / "app.previous"
    if app.exists():
        shutil.rmtree(prev, ignore_errors=True)
        app.rename(prev)
    new.rename(app)
    return label


def model_search_dirs():
    """Places a Whisper model may already be on this computer (Hugging Face cache layout)."""
    dirs = []
    if os.environ.get("FT_ASSISTANT_MODEL_SOURCE"):
        dirs.append(Path(os.environ["FT_ASSISTANT_MODEL_SOURCE"]))
    if os.environ.get("HF_HUB_CACHE"):
        dirs.append(Path(os.environ["HF_HUB_CACHE"]))
    if os.environ.get("HF_HOME"):
        dirs.append(Path(os.environ["HF_HOME"]) / "hub")
    dirs.append(home() / ".cache" / "huggingface" / "hub")
    if not IS_WINDOWS:
        dirs.append(home() / ".local" / "share" / "voice-dictation" / "models")   # earlier tool
    return dirs


MODEL_FILES = ("model.bin", "config.json", "tokenizer.json")


def complete_model_dir(d):
    """True if `d` holds a usable model (real files, not broken links)."""
    return all((Path(d) / f).is_file() and (Path(d) / f).stat().st_size > 0 for f in MODEL_FILES)


def find_model(name, search=None):
    """A complete snapshot folder of the model in a Hugging Face style cache, or None."""
    for d in search if search is not None else model_search_dirs():
        for snap in sorted(Path(d).glob(f"models--*--faster-whisper-{name}/snapshots/*")):
            if complete_model_dir(snap):
                return snap
    return None


def link_files(src, dest):
    """Put the model's files into `dest` as hard links to the real files (no extra disk space,
    independent of the original: deleting either keeps the other). Links inside caches are
    followed to the real file. If hard links aren't possible (different drive), copy."""
    dest.mkdir(parents=True, exist_ok=True)
    copied = False
    for f in Path(src).iterdir():
        real, t = f.resolve(), dest / f.name
        if not real.is_file() or t.exists():
            continue
        try:
            os.link(real, t)
        except OSError:
            shutil.copy2(real, t)
            copied = True
    return copied


def install_model(install_dir, gpu):
    """The model lives in <dir>/models/<name> as plain files (no symlinks: they break under
    Wine and on Windows without developer mode). Returns that folder."""
    name = GPU_MODEL if gpu else CPU_MODEL
    target = Path(install_dir) / "models" / name
    if complete_model_dir(target):
        say(f"  The Whisper model ({name}) is already there.")
        return target
    found = find_model(name)
    if found:
        copied = link_files(found, target)
        say(f"  Reusing the Whisper model already on this computer ({found.parents[2]})"
            + (" (copied: different drive)." if copied else ", no download and no extra disk space."))
        return target
    size = "about 1.6 GB" if name == GPU_MODEL else "about 500 MB"
    say(f"  Downloading the Whisper model ({name}, {size}). The progress bar below shows how far")
    say("  along it is.")
    # Downloaded directly (not through faster-whisper's helper, which hides the progress bar).
    run([python_exe(install_dir), "-c",
         "import sys; from faster_whisper.utils import _MODELS; "
         "from huggingface_hub import snapshot_download; "
         "snapshot_download(_MODELS.get(sys.argv[1], sys.argv[1]), local_dir=sys.argv[2], "
         "allow_patterns=['config.json', 'preprocessor_config.json', 'model.bin', "
         "'tokenizer.json', 'vocabulary.*'])", name, target])
    if not complete_model_dir(target):
        raise RuntimeError("the Whisper model download is incomplete; run setup again")
    return target


def write_launchers(install_dir, gpu, model, gpu_libs="pip"):
    d = Path(install_dir)
    py = python_exe(d)
    env = {
        "FT_ASSISTANT_DATA_DIR": str(d),
        "FT_ASSISTANT_MODELS_DIR": str(d / "models"),
        "FT_ASSISTANT_MODEL": model,
        "FT_ASSISTANT_DEVICE": "cuda" if gpu else "cpu",
        "HF_HUB_OFFLINE": "1",
        "PYTHONNOUSERSITE": "1",     # ignore any Python packages the user installed elsewhere
    }
    launchers = {}
    for name, module in (("ft-assistant", "ft_assistant"),
                         ("ft-assistant-setup", "ft_assistant.open_setup"),
                         ("ft-assistant-uninstall", None)):
        if IS_WINDOWS:
            path = d / (name + ".cmd")
            # Start from the install folder: Python looks for modules in the current folder first.
            lines = ["@echo off", f'cd /d "{d}"'] + [f'set "{k}={v}"' for k, v in env.items()]
            lines.append(f'set "PYTHONPATH={d / "app"}"')
            if gpu and gpu_libs == "pip":
                nv = d / "python" / "Lib" / "site-packages" / "nvidia"
                lines.append(f'set "PATH={nv / "cublas" / "bin"};{nv / "cudnn" / "bin"};%PATH%"')
            if module:
                lines.append(f'start "" "{pythonw_exe(d)}" -m {module}')
            else:
                lines.append(f'"{py}" "{d / "install.py"}" uninstall --dir "{d}"')
            path.write_text("\r\n".join(lines) + "\r\n", encoding="utf-8")
        else:
            path = d / name
            lines = ["#!/bin/bash", "# Written by the FT Assistant installer.",
                     # Start from the install folder: Python looks for modules in the current
                     # folder first, so starting elsewhere could pick up the wrong copy.
                     f'cd "{d}" || exit 1']
            lines += [f'export {k}="{v}"' for k, v in env.items()]
            lines.append(f'export PYTHONPATH="{d / "app"}"')
            # A system upgrade can replace the computer's Python under a venv; say so clearly.
            lines.append(f'"{py}" -c "" 2>/dev/null || {{ notify-send -a "{APP_NAME}" "{APP_NAME} needs '
                         f'a repair" "Its Python stopped working (often after a system upgrade). Run '
                         f'FT-Assistant-setup.cmd again to repair it."; exit 1; }}')
            if gpu and gpu_libs == "pip":
                lines.append('SP=$("' + str(py) + '" -c "import site;print(site.getsitepackages()[0])")')
                lines.append('export LD_LIBRARY_PATH="$SP/nvidia/cublas/lib:$SP/nvidia/cudnn/lib'
                             '${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"')
            if module:
                lines.append(f'exec "{py}" -m {module} "$@"')
            else:
                lines.append(f'exec "{py}" "{d / "install.py"}" uninstall --dir "{d}" "$@"')
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            path.chmod(0o755)
        launchers[name] = path
    return launchers


def _desktop_entry(name, comment, exec_path, terminal=False, extra=""):
    return (f"[Desktop Entry]\nType=Application\nName={name}\nComment={comment}\n"
            f'Exec="{exec_path}"\nTerminal={"true" if terminal else "false"}\n'
            f"Categories=Utility;Accessibility;\n{extra}")


def write_shortcuts(launchers, autostart=True):
    """Login entry and app-menu entries (Linux .desktop files; Windows .cmd shortcuts)."""
    written = []
    if IS_WINDOWS:
        # Windows shortcuts (.lnk) need a COM helper; plain .cmd files in the Start Menu work.
        md = menu_dir()
        md.mkdir(parents=True, exist_ok=True)
        for label, key in ((APP_NAME, "ft-assistant"), (APP_NAME + " setup", "ft-assistant-setup"),
                           ("Uninstall " + APP_NAME, "ft-assistant-uninstall")):
            p = md / (label + ".cmd")
            p.write_text(f'@call "{launchers[key]}"\r\n', encoding="utf-8")
            written.append(p)
        if autostart:
            p = autostart_dir() / (APP_NAME + ".cmd")
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(f'@call "{launchers["ft-assistant"]}"\r\n', encoding="utf-8")
            written.append(p)
        return written
    md = menu_dir()
    md.mkdir(parents=True, exist_ok=True)
    entries = {
        "ft-assistant.desktop": _desktop_entry(APP_NAME, "Push-to-talk dictation",
                                               launchers["ft-assistant"]),
        "ft-assistant-setup.desktop": _desktop_entry(APP_NAME + " setup", "Choose your assistant "
                                                     "and Assistant key", launchers["ft-assistant-setup"]),
        "ft-assistant-uninstall.desktop": _desktop_entry("Uninstall " + APP_NAME, "Remove FT "
                                                         "Assistant", launchers["ft-assistant-uninstall"],
                                                         terminal=True),
    }
    for fname, text in entries.items():
        (md / fname).write_text(text, encoding="utf-8")
        written.append(md / fname)
    if autostart:
        ad = autostart_dir()
        ad.mkdir(parents=True, exist_ok=True)
        p = ad / "ft-assistant.desktop"
        p.write_text(_desktop_entry(APP_NAME, "Push-to-talk dictation", launchers["ft-assistant"],
                                    extra="X-GNOME-Autostart-enabled=true\nX-GNOME-Autostart-Delay=5\n"),
                     encoding="utf-8")
        written.append(p)
    return written


UNINSTALL_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\FTAssistant"


def register_windows_app(install_dir, launchers, version):
    """Windows: list FT Assistant under Settings -> Apps (per user, no admin needed)."""
    if not IS_WINDOWS:
        return
    import winreg
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY) as k:
        for name, value in (("DisplayName", APP_NAME), ("Publisher", "freethought78"),
                            ("DisplayVersion", version), ("InstallLocation", str(install_dir)),
                            ("UninstallString", f'"{launchers["ft-assistant-uninstall"]}"')):
            winreg.SetValueEx(k, name, 0, winreg.REG_SZ, value)
        for name in ("NoModify", "NoRepair"):
            winreg.SetValueEx(k, name, 0, winreg.REG_DWORD, 1)


def unregister_windows_app():
    if not IS_WINDOWS:
        return
    import winreg
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY)
    except OSError:
        pass


def app_version(install_dir):
    try:
        text = (Path(install_dir) / "app" / "ft_assistant" / "__init__.py").read_text()
        return text.split('__version__ = "', 1)[1].split('"', 1)[0]
    except (OSError, IndexError):
        return ""


def write_vocabulary():
    p = config_dir() / "vocabulary.txt"
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("# Words or names Whisper gets wrong go here, one per line.\n"
                     "# The model is nudged toward these spellings. Lines starting with # are ignored.\n"
                     "Claude\nOpenCode\n", encoding="utf-8")


def stop_running_app():
    """Stop a running FT Assistant (it holds a lock file; its process id is written in it)."""
    lock = config_dir() / ".lock"
    try:
        pid = int(lock.read_text().strip() or 0)
    except (OSError, ValueError):
        return
    if pid <= 0:
        return
    try:
        if IS_WINDOWS:
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
        else:
            os.kill(pid, 15)
        time.sleep(1)
        say("Stopped the running FT Assistant.")
    except (OSError, ProcessLookupError):
        pass


def start_app(launchers):
    exe = launchers["ft-assistant"]
    cmd = ["cmd", "/c", str(exe)] if IS_WINDOWS else [str(exe)]
    subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, start_new_session=not IS_WINDOWS)


def save_manifest(install_dir, info):
    (Path(install_dir) / "install.json").write_text(json.dumps(info, indent=2), encoding="utf-8")


def load_manifest(install_dir):
    try:
        return json.loads((Path(install_dir) / "install.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def copy_self(install_dir):
    """Keep a copy of this installer in the install folder (used for update and uninstall)."""
    dest = Path(install_dir) / "install.py"
    if Path(__file__).resolve() != dest.resolve():
        shutil.copyfile(__file__, dest)


# ---------------------------------------------------------------- commands

def cmd_install(a):
    d = Path(a.dir).expanduser().resolve()
    gpu = a.gpu == "yes"
    d.mkdir(parents=True, exist_ok=True)
    stop_running_app()
    step(3, "Installing the speech engine")
    try:
        install_packages(d, gpu, a.gpu_libs)
    except PackagesFailed as e:
        say(f"Installing the speech engine failed: {e}")
        raise SystemExit(3)            # the setup script may retry with a downloaded Python
    step(4, "Installing the FT Assistant program")
    label = fetch_app(d, a.source)
    say("  Done.")
    step(5, "Getting the Whisper speech model")
    model = str(install_model(d, gpu))       # folder with the model's files
    step(6, "Adding menu entries and finishing")
    copy_self(d)
    launchers = write_launchers(d, gpu, model, a.gpu_libs)
    shortcuts = write_shortcuts(launchers, autostart=not a.no_autostart)
    register_windows_app(d, launchers, app_version(d))
    write_vocabulary()
    save_manifest(d, {"installed": time.strftime("%Y-%m-%d %H:%M"), "gpu": gpu, "model": model,
                      "gpu_libs": a.gpu_libs, "python": a.python_source, "source": label,
                      "shortcuts": [str(p) for p in shortcuts]})
    say("")
    say(f"{APP_NAME} is installed in {d}")
    if not a.no_start:
        start_app(launchers)
        say("It's starting now. The setup window opens so you can choose your assistant.")


def _rollback(d):
    """Put the previous program (and installer) back after a failed update."""
    prev = d / "app.previous"
    if prev.exists():
        shutil.rmtree(d / "app", ignore_errors=True)
        prev.rename(d / "app")
    if (d / "install.py.previous").exists():
        os.replace(d / "install.py.previous", d / "install.py")


def cmd_update(a):
    d = Path(a.dir).expanduser().resolve()
    info = load_manifest(d)
    stop_running_app()
    try:
        step(1, "Downloading the new version", total=2)
        label = fetch_app(d, a.source)
    except Exception as e:
        say(f"Update failed ({e}); nothing was changed.")
        start_app(write_launchers(d, info.get("gpu", False), info.get("model", CPU_MODEL),
                                  info.get("gpu_libs", "pip")))
        raise SystemExit(1)
    info["source"] = label
    save_manifest(d, info)
    new_installer = d / "install.py.new"
    if new_installer.exists():
        # Hand over to the release's own installer, so its newer logic does the rest.
        shutil.copyfile(d / "install.py", d / "install.py.previous")
        os.replace(new_installer, d / "install.py")
        rc = subprocess.run([str(python_exe(d)), str(d / "install.py"), "finish-update",
                             "--dir", str(d)] + (["--no-start"] if a.no_start else []),
                            env=dict(os.environ, PYTHONNOUSERSITE="1")).returncode
        raise SystemExit(rc)
    finish_update(d, a.no_start)


def finish_update(d, no_start=False):
    """Second half of an update, run by the new installer: packages, launchers, restart."""
    info = load_manifest(d)
    try:
        step(2, "Updating the speech engine (only what changed is downloaded)", total=2)
        install_packages(d, info.get("gpu", False), info.get("gpu_libs", "pip"))
    except Exception as e:
        _rollback(d)
        say(f"Update failed ({e}); the previous version was put back.")
        start_app(write_launchers(d, info.get("gpu", False), info.get("model", CPU_MODEL),
                                  info.get("gpu_libs", "pip")))
        raise SystemExit(1)
    info["updated"] = time.strftime("%Y-%m-%d %H:%M")
    save_manifest(d, info)
    launchers = write_launchers(d, info.get("gpu", False), info.get("model", CPU_MODEL),
                                info.get("gpu_libs", "pip"))
    register_windows_app(d, launchers, app_version(d))
    if not no_start:
        start_app(launchers)
    say("Updated. The previous version is kept in app.previous for rollback.")


def cmd_finish_update(a):
    finish_update(Path(a.dir).expanduser().resolve(), a.no_start)


def cmd_uninstall(a):
    d = Path(a.dir).expanduser().resolve()
    info = load_manifest(d)
    if not (d / "install.json").exists():
        say(f"No FT Assistant installation found in {d}.")
        raise SystemExit(1)
    if not a.yes:
        say(f"This removes FT Assistant from {d}:")
        say("the program, its Python, the speech engine, GPU libraries, the Whisper model,")
        say("and its menu and login entries. Claude Code and OpenCode stay installed.")
        if input("Type yes to uninstall: ").strip().lower() != "yes":
            say("Nothing was removed.")
            return
    say("Removing FT Assistant...")
    stop_running_app()
    for p in info.get("shortcuts", []):
        try:
            Path(p).unlink()
        except OSError:
            pass
    unregister_windows_app()
    if not a.keep_settings:
        shutil.rmtree(config_dir(), ignore_errors=True)
    if IS_WINDOWS:
        # Windows can't delete the Python that's running this; remove what we can now and let
        # a small detached command delete the rest a few seconds after we exit.
        for child in d.iterdir():
            if child.name != "python":
                shutil.rmtree(child, ignore_errors=True) if child.is_dir() else child.unlink()
        subprocess.Popen(f'cmd /c ping -n 4 127.0.0.1 >nul & rmdir /s /q "{d}"',
                         creationflags=0x08000000 | 0x00000008)   # no window, detached
    else:
        shutil.rmtree(d, ignore_errors=True)
    say("FT Assistant was removed." + (" Your settings were kept." if a.keep_settings else ""))
    say("Claude Code and OpenCode are still installed; remove them separately if you want.")


def main(argv=None):
    p = argparse.ArgumentParser(description="FT Assistant installer")
    sub = p.add_subparsers(dest="command", required=True)
    i = sub.add_parser("install")
    i.add_argument("--dir", required=True)
    i.add_argument("--gpu", choices=("yes", "no"), required=True)
    i.add_argument("--gpu-libs", choices=("pip", "system"), default="pip")
    i.add_argument("--python-source", choices=("system", "standalone"), default="standalone")
    i.add_argument("--source")
    i.add_argument("--no-autostart", action="store_true")
    i.add_argument("--no-start", action="store_true")
    u = sub.add_parser("update")
    u.add_argument("--dir", required=True)
    u.add_argument("--source")
    u.add_argument("--no-start", action="store_true")
    f = sub.add_parser("finish-update")
    f.add_argument("--dir", required=True)
    f.add_argument("--no-start", action="store_true")
    x = sub.add_parser("uninstall")
    x.add_argument("--dir", required=True)
    x.add_argument("--keep-settings", action="store_true")
    x.add_argument("--yes", action="store_true")
    for sp in (i, u, f, x):
        sp.add_argument("--pause", action="store_true",
                        help="wait for Enter at the end (when run in its own window)")
    a = p.parse_args(argv)
    try:
        {"install": cmd_install, "update": cmd_update, "finish-update": cmd_finish_update,
         "uninstall": cmd_uninstall}[a.command](a)
    finally:
        if a.pause:
            input("\nPress Enter to close this window. ")


if __name__ == "__main__":
    main()
