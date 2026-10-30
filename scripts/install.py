#!/usr/bin/env python3
"""
CHAOS installer. Run it through setup.bat (Windows) or setup.sh (macOS/Linux),
which find a suitable Python first; running it directly with Python 3.10+ also works.

Safe to re-run: every step checks before it acts, so a second run only fixes
what's missing (e.g. swaps in a CUDA build of PyTorch after you install an
NVIDIA driver).
"""

import argparse
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENV = ROOT / "venv"
IS_WINDOWS = os.name == "nt"
VENV_PY = VENV / ("Scripts/python.exe" if IS_WINDOWS else "bin/python")
MIN_PYTHON = (3, 10)
# numba first: see the WinError 1114 note in desktop_app/main_gui.py.
VERIFY_IMPORTS = "import numba, torch, cv2, whisper, easyocr, librosa, yaml, pandas, thefuzz, PyQt6.QtWidgets, webview"
FFMPEG_ZIP_URL ="https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"

# Both are stdlib-only, so they import fine before any dependencies are installed.
sys.path.insert(0, str(ROOT))
from chaos_lib.clipper import _get_ffmpeg, _REPO_BIN  # noqa: E402
from desktop_app.gui.utils.system_detector import SystemDetector  # noqa: E402


class InstallError(Exception):
    pass


def say(msg: str = ""):
    print(msg, flush=True)


def run(cmd: list, what: str):
    say(f"     > {' '.join(str(c) for c in cmd)}")
    if subprocess.call([str(c) for c in cmd]) != 0:
        raise InstallError(f"{what} failed (see the output above).")


def venv_eval(code: str):
    """stdout of `code` run in the venv, or None if it fails."""
    try:
        out = subprocess.run([str(VENV_PY), "-c", code], capture_output=True, text=True, timeout=300)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return out.stdout.strip() if out.returncode == 0 else None


def ensure_venv():
    if venv_eval("import sys; print(sys.version_info >= %r)" % (MIN_PYTHON,)) == "True":
        say(f"     Using existing environment: {VENV}")
    else:
        if VENV.exists():
            say("     Existing venv is broken or too old; rebuilding it.")
            shutil.rmtree(VENV)
        run([sys.executable, "-m", "venv", VENV], "Creating the virtual environment")
    run([VENV_PY, "-m", "pip", "install", "--upgrade", "--quiet", "pip"], "Upgrading pip")


def torch_target():
    """(index_url or None for PyPI, human description)."""
    system = platform.system()
    if system == "Darwin":
        return None, "PyPI build (Apple Silicon GPU via MPS)"
    gpu = SystemDetector.detect_nvidia_gpu()
    if gpu.get("present"):
        tag = SystemDetector.pick_cuda_wheel_tag(gpu.get("max_cuda_version"))
        if tag:
            return f"https://download.pytorch.org/whl/{tag}", f"CUDA {tag} build for {gpu['name']}"
        say(f"     WARNING: {gpu['name']} found, but its driver is too old for PyTorch's CUDA builds.")
        say("     Update your NVIDIA driver and re-run setup to enable GPU acceleration.")
    # PyPI's Linux torch bundles ~2 GB of CUDA libraries; skip them without a GPU.
    if system == "Linux":
        return "https://download.pytorch.org/whl/cpu", "CPU-only build"
    return None, "CPU-only build"


def ensure_torch():
    index, desc = torch_target()
    want_cuda = bool(index and "/cu" in index)
    say(f"     Target: {desc}")

    installed = venv_eval("import torch; print(torch.__version__, torch.version.cuda is not None)")
    if installed:
        version, is_cuda_build = installed.split()
        if is_cuda_build == "True" or not want_cuda:
            say(f"     torch {version} already installed.")
            return
        say(f"     torch {version} is a CPU-only build; replacing it with the CUDA build.")
        run([VENV_PY, "-m", "pip", "uninstall", "-y", "torch", "torchvision", "torchaudio"],
            "Removing CPU-only PyTorch")

    say("     This is the big download (up to ~3 GB). Grab a coffee.")
    cmd = [VENV_PY, "-m", "pip", "install", "torch", "torchvision", "torchaudio"]
    if index:
        cmd += ["--index-url", index]
    run(cmd, "Installing PyTorch")


def ensure_requirements():
    cmd = [VENV_PY, "-m", "pip", "install", "-r", ROOT / "requirements.txt"]
    # Still run pip on re-runs (it picks up new requirements), but skip its
    # wall of "Requirement already satisfied" when everything already imports.
    if venv_eval(VERIFY_IMPORTS) is not None:
        cmd.append("--quiet")
    run(cmd, "Installing requirements.txt")


def _ffmpeg_path():
    try:
        return _get_ffmpeg()
    except FileNotFoundError:
        return None


def _download_ffmpeg_windows():
    say("     Downloading a portable FFmpeg into bin\\ ...")
    os.makedirs(_REPO_BIN, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        archive = os.path.join(tmp, "ffmpeg.zip")
        urllib.request.urlretrieve(FFMPEG_ZIP_URL, archive)
        with zipfile.ZipFile(archive) as zf:
            for member in zf.namelist():
                name = member.rsplit("/", 1)[-1]
                if member.endswith(("/bin/ffmpeg.exe", "/bin/ffprobe.exe")):
                    with zf.open(member) as src, open(os.path.join(_REPO_BIN, name), "wb") as dst:
                        shutil.copyfileobj(src, dst)


def ensure_ffmpeg():
    path = _ffmpeg_path()
    if path:
        say(f"     Found: {path}")
        return

    system = platform.system()
    if system == "Windows":
        if shutil.which("winget"):
            subprocess.call(["winget", "install", "-e", "--id", "Gyan.FFmpeg",
                             "--accept-package-agreements", "--accept-source-agreements"])
        if not _ffmpeg_path():
            try:
                _download_ffmpeg_windows()
            except OSError as e:
                say(f"     Download failed: {e}")
    elif system == "Darwin":
        if shutil.which("brew"):
            subprocess.call(["brew", "install", "ffmpeg"])
        else:
            say("     Homebrew not found. Install it from https://brew.sh, then: brew install ffmpeg")
    else:
        for manager, cmd in [("apt-get", ["sudo", "apt-get", "install", "-y", "ffmpeg"]),
                             ("dnf", ["sudo", "dnf", "install", "-y", "ffmpeg"]),
                             ("pacman", ["sudo", "pacman", "-S", "--noconfirm", "ffmpeg"]),
                             ("zypper", ["sudo", "zypper", "install", "-y", "ffmpeg"])]:
            if shutil.which(manager):
                say(f"     Installing via {manager} (may ask for your password):")
                subprocess.call(cmd)
                break

    path = _ffmpeg_path()
    if not path:
        raise InstallError("Could not install FFmpeg. Install it manually (https://ffmpeg.org/download.html), "
                           "make sure `ffmpeg` is on your PATH, then re-run setup.")
    say(f"     Installed: {path}")


def verify():
    out = venv_eval(
        VERIFY_IMPORTS + "\n"
        "if torch.cuda.is_available(): d = 'GPU (CUDA): ' + torch.cuda.get_device_name(0)\n"
        "elif torch.backends.mps.is_available(): d = 'GPU (Apple MPS)'\n"
        "else: d = 'CPU only'\n"
        "print(d)"
    )
    if out is None:
        raise InstallError("Dependencies installed, but importing them failed. "
                           f"Run `{VENV_PY} run_desktop_app.py` to see the error.")
    say(f"     All imports OK. Processing device: {out}")


def ensure_models():
    # Run from the repo root: config.yaml's data_folder is relative to it.
    if subprocess.call([str(VENV_PY), "-m", "chaos_lib.models"], cwd=ROOT) != 0:
        raise InstallError("Downloading the AI models failed. Check your internet connection and run setup again.")


def create_shortcuts(desktop: bool):
    if IS_WINDOWS:
        # pythonw.exe: no console window. run_desktop_app.py hides the console
        # tools it spawns and logs output to chaos.log.
        ps = (
            "$s = New-Object -ComObject WScript.Shell;"
            "foreach ($dir in $env:CHAOS_LINK_DIRS.Split('|')) {"
            "  $l = $s.CreateShortcut((Join-Path $dir 'CHAOS.lnk'));"
            "  $l.TargetPath = $env:CHAOS_PY;"
            "  $l.Arguments = '\"' + $env:CHAOS_ENTRY + '\"';"
            "  $l.WorkingDirectory = $env:CHAOS_ROOT;"
            "  $l.WindowStyle = 1;"
            "  $l.Description = 'CHAOS: CS2 highlight finder';"
            "  $l.Save() }"
        )
        folders = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "[Environment]::GetFolderPath('Programs'); [Environment]::GetFolderPath('Desktop')"],
            capture_output=True, text=True,
        ).stdout.splitlines()
        dirs = folders[:1] + (folders[1:2] if desktop else [])
        env = dict(os.environ, CHAOS_LINK_DIRS="|".join(dirs), CHAOS_PY=str(VENV / "Scripts/pythonw.exe"),
                   CHAOS_ENTRY=str(ROOT / "run_desktop_app.py"), CHAOS_ROOT=str(ROOT))
        if subprocess.call(["powershell", "-NoProfile", "-Command", ps], env=env) == 0:
            say("     Added CHAOS to the Start Menu" + (" and Desktop." if desktop else "."))
        else:
            say("     WARNING: Could not create shortcuts.")
    elif platform.system() == "Linux":
        apps = Path.home() / ".local/share/applications"
        apps.mkdir(parents=True, exist_ok=True)
        (apps / "chaos.desktop").write_text(
            "[Desktop Entry]\nType=Application\nName=CHAOS\n"
            "Comment=CS2 highlight finder\n"
            f'Exec="{VENV_PY}" "{ROOT / "run_desktop_app.py"}"\n'
            f"Path={ROOT}\nTerminal=false\nCategories=Video;\n"
        )
        say("     Added CHAOS to your applications menu.")


def main():
    parser = argparse.ArgumentParser(description="Install CHAOS and its dependencies.")
    parser.add_argument("--desktop-shortcut", action="store_true", help="also put a shortcut on the Desktop (Windows)")
    parser.add_argument("--no-shortcut", action="store_true", help="don't create any shortcuts")
    args = parser.parse_args()

    if sys.version_info < MIN_PYTHON:
        say(f"ERROR: CHAOS needs Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+, this is {platform.python_version()}.")
        return 1

    steps = [
        ("Python environment", ensure_venv),
        ("PyTorch", ensure_torch),
        ("Python packages", ensure_requirements),
        ("FFmpeg", ensure_ffmpeg),
        ("Checking the install", verify),
        ("AI models", ensure_models),
    ]
    if not args.no_shortcut:
        steps.append(("Shortcuts", lambda: create_shortcuts(args.desktop_shortcut)))

    say(f"Installing CHAOS in {ROOT} (Python {platform.python_version()})")
    for i, (name, fn) in enumerate(steps, 1):
        say(f"\n[{i}/{len(steps)}] {name}")
        try:
            fn()
        except InstallError as e:
            say(f"\nSETUP FAILED: {e}")
            say("Fix the problem above and run setup again; finished steps are skipped.")
            return 1

    say("\nCHAOS is installed.")
    if IS_WINDOWS and not args.no_shortcut:
        say("Launch it from the Start Menu (search \"CHAOS\"), or run:")
    else:
        say("Launch it with:")
    say(f'  "{VENV_PY}" "{ROOT / "run_desktop_app.py"}"')
    return 0


if __name__ == "__main__":
    sys.exit(main())
