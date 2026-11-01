#!/usr/bin/env python3
"""
Second stage of the one-click installer.

Install-Windows.bat / Install-Mac.command create the app's private Python 3.10
environment (.venv) and then run this script with it. It:
  1. checks the install location (Windows 260-character path limit),
  2. installs the dependencies (install_requirements.py),
  3. checks that the SLEAP model is present,
  4. creates a Desktop shortcut (plus a Start-menu entry on Windows).

Set BEE_SHORTCUT_DIR to put the shortcuts somewhere else (used for testing).
"""

import json
import os
import platform
import plistlib
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

APP_DIR = Path(__file__).resolve().parent.parent
APP_NAME = "Bee Interaction Detector"
BUNDLE_ID = "il.ac.huji.bee-interaction-detector"
TOOLS_DIR = APP_DIR / ".tools"
ICON_PNG = APP_DIR / "media" / "app_icon.png"

# TensorFlow ships files with very long names. Without Windows long-path
# support, installing under a long folder path fails half-way through.
MAX_WINDOWS_APP_DIR = 80


def step(title):
    print("\n=== " + title, flush=True)


# ── Install location ──────────────────────────────────────────────────────────

def windows_long_paths_enabled() -> bool:
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                            r"SYSTEM\CurrentControlSet\Control\FileSystem") as key:
            return winreg.QueryValueEx(key, "LongPathsEnabled")[0] == 1
    except OSError:
        return False


def location_problem(app_dir, is_windows, long_paths_enabled) -> Optional[str]:
    """Why this folder can't be used, or None if it's fine."""
    if is_windows and not long_paths_enabled and len(str(app_dir)) > MAX_WINDOWS_APP_DIR:
        return (
            "The program folder path is too long for Windows:\n"
            "    {}\n"
            "Move the whole folder somewhere short, for example  C:\\BeeDetector ,\n"
            "and run Install-Windows.bat again from there.".format(app_dir)
        )
    return None


def location_warning(app_dir) -> Optional[str]:
    if "onedrive" in str(app_dir).lower():
        return ("The program folder is inside OneDrive. The install is ~3 GB and OneDrive "
                "will try to sync it; a folder like C:\\BeeDetector works better.")
    return None


# ── Model ─────────────────────────────────────────────────────────────────────

def model_path(app_dir=APP_DIR) -> Path:
    cfg = json.loads((app_dir / "config.json").read_text())
    p = Path(cfg.get("model_path", ""))
    return p if p.is_absolute() else app_dir / p


# ── Smoke test ────────────────────────────────────────────────────────────────

def pipeline_commands(app_dir=APP_DIR):
    """One cheap command per pipeline program. `--help` imports the whole program
    (SLEAP -> TensorFlow, NAPS, OpenCV...), so a broken install fails here
    instead of in the middle of a user's first run."""
    sys.path.insert(0, str(app_dir))
    from video_to_csv import tool  # same resolution the pipeline uses

    py = sys.executable
    return [
        ("SLEAP inference", [tool("sleap-track"), "--help"]),
        ("NAPS identity correction", [tool("naps-track"), "--help"]),
        ("SLEAP CSV export", [tool("sleap-convert"), "--help"]),
        ("Interaction detection", [py, str(app_dir / "find_interactions_by_antennation.py"), "--help"]),
        ("Group split", [py, str(app_dir / "split_to_groups.py"), "--help"]),
    ]


def failing_commands(commands, timeout=600):
    """Run each (name, cmd); return [(name, output tail)] for the ones that fail."""
    failures = []
    for name, cmd in commands:
        print("  - {} ...".format(name), flush=True)
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, errors="replace",
                                 timeout=timeout, cwd=str(APP_DIR))
            ok, output = res.returncode == 0, (res.stdout or "") + (res.stderr or "")
        except (OSError, subprocess.TimeoutExpired) as exc:
            ok, output = False, str(exc)
        if not ok:
            failures.append((name, "\n".join(output.strip().splitlines()[-15:])))
    return failures


# ── Icons ─────────────────────────────────────────────────────────────────────

def make_icon(fmt) -> Optional[Path]:
    """Build .ico (Windows) or .icns (macOS) from media/app_icon.png."""
    if not ICON_PNG.exists():
        return None
    from PIL import Image  # installed by requirements.txt

    TOOLS_DIR.mkdir(exist_ok=True)
    out = TOOLS_DIR / "app_icon.{}".format(fmt)
    img = Image.open(ICON_PNG).convert("RGBA")
    if fmt == "ico":
        img.save(out, sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)])
    else:
        img.save(out)
    return out


# ── Shortcuts ─────────────────────────────────────────────────────────────────

def _windows_folder(name) -> Optional[Path]:
    """Real location of a shell folder ('Desktop', 'Programs'), incl. OneDrive redirection."""
    out = subprocess.run(
        ["powershell", "-NoProfile", "-Command", "[Environment]::GetFolderPath('{}')".format(name)],
        capture_output=True, text=True,
    )
    path = out.stdout.strip()
    return Path(path) if path else None


def create_windows_shortcut(lnk_path, icon=None):
    # type: (Path, Optional[Path]) -> Path
    pythonw = APP_DIR / ".venv" / "Scripts" / "pythonw.exe"   # no console window
    env = dict(os.environ,
               BEE_LNK=str(lnk_path), BEE_TARGET=str(pythonw),
               BEE_ARGS='"{}"'.format(APP_DIR / "gui.py"), BEE_WORKDIR=str(APP_DIR),
               BEE_ICON=str(icon) if icon else str(pythonw))
    # Paths go through environment variables, so spaces/quotes/non-ASCII are safe.
    script = (
        "$s = (New-Object -ComObject WScript.Shell).CreateShortcut($env:BEE_LNK); "
        "$s.TargetPath = $env:BEE_TARGET; $s.Arguments = $env:BEE_ARGS; "
        "$s.WorkingDirectory = $env:BEE_WORKDIR; $s.IconLocation = $env:BEE_ICON; "
        "$s.Description = 'Detect bee antennation interactions in videos'; $s.Save()"
    )
    lnk_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
                   env=env, check=True)
    return lnk_path


def create_mac_app(dest_dir, icns=None, app_dir=APP_DIR):
    # type: (Path, Optional[Path], Path) -> Path
    """A minimal .app bundle that starts the GUI with the app's own Python."""
    app = Path(dest_dir) / "{}.app".format(APP_NAME)
    if app.exists():
        shutil.rmtree(str(app))
    macos = app / "Contents" / "MacOS"
    resources = app / "Contents" / "Resources"
    macos.mkdir(parents=True)
    resources.mkdir()

    info = {
        "CFBundleName": APP_NAME,
        "CFBundleDisplayName": APP_NAME,
        "CFBundleIdentifier": BUNDLE_ID,
        "CFBundleExecutable": "launcher",
        "CFBundlePackageType": "APPL",
        "CFBundleVersion": "1.0",
        "CFBundleShortVersionString": "1.0",
        "NSHighResolutionCapable": True,
        "LSMinimumSystemVersion": "11.0",
    }
    if icns and Path(icns).exists():
        shutil.copy(str(icns), str(resources / "app_icon.icns"))
        info["CFBundleIconFile"] = "app_icon"
    with open(str(app / "Contents" / "Info.plist"), "wb") as fh:
        plistlib.dump(info, fh)

    launcher = macos / "launcher"
    launcher.write_text(
        "#!/bin/bash\n"
        "APP_DIR={app_dir}\n"
        'PY="$APP_DIR/.venv/bin/python"\n'
        'if [ ! -x "$PY" ]; then\n'
        "  /usr/bin/osascript -e 'display alert \"{name}\" message \"The program folder "
        "was moved or deleted. Run Install-Mac.command again from the program folder.\"'\n"
        "  exit 1\n"
        "fi\n"
        'mkdir -p "$APP_DIR/.tools"\n'
        'cd "$APP_DIR" || exit 1\n'
        'exec "$PY" "$APP_DIR/gui.py" >>"$APP_DIR/.tools/gui.log" 2>&1\n'.format(
            app_dir=shlex.quote(str(app_dir)), name=APP_NAME)
    )
    launcher.chmod(0o755)
    os.utime(str(app), None)   # nudge Finder to pick up the icon
    return app


def create_shortcuts(is_windows, is_mac):
    override = os.environ.get("BEE_SHORTCUT_DIR")
    if is_windows:
        icon = make_icon("ico")
        targets = [Path(override)] if override else [
            d for d in (_windows_folder("Desktop"), _windows_folder("Programs")) if d]
        made = []
        for folder in targets:
            made.append(create_windows_shortcut(folder / "{}.lnk".format(APP_NAME), icon))
        return made
    if is_mac:
        icns = make_icon("icns")
        dest = Path(override) if override else Path.home() / "Desktop"
        dest.mkdir(parents=True, exist_ok=True)
        return [create_mac_app(dest, icns)]
    return []


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    is_windows = platform.system() == "Windows"
    is_mac = platform.system() == "Darwin"
    print("{} - setting up in: {}".format(APP_NAME, APP_DIR))

    step("Checking the install location")
    problem = location_problem(APP_DIR, is_windows, is_windows and windows_long_paths_enabled())
    if problem:
        print("[ERROR] " + problem)
        return 1
    warning = location_warning(APP_DIR)
    print("[WARNING] " + warning if warning else "[OK] Location is fine.")

    step("Installing the required packages (about 3 GB - this is the long part)")
    try:
        subprocess.run([sys.executable, str(APP_DIR / "install_requirements.py")], check=True)
    except subprocess.CalledProcessError:
        print("[ERROR] Installing the packages failed - see the messages above.")
        return 1

    step("Checking that every part of the pipeline starts (about a minute)")
    failures = failing_commands(pipeline_commands())
    if failures:
        for name, output in failures:
            print("\n[ERROR] {} does not start:\n{}".format(name, output))
        return 1
    print("[OK] All pipeline programs start.")

    step("Checking the bee-tracking model")
    model = model_path()
    if model.is_dir():
        print("[OK] Model found: {}".format(model.name))
    else:
        print("[WARNING] Model folder not found: {}\n"
              "          Use 'Update Model' in the program to select the model folder.".format(model))

    step("Creating the program shortcut")
    try:
        for path in create_shortcuts(is_windows, is_mac):
            print("[OK] Created: {}".format(path))
    except Exception as exc:  # a missing shortcut shouldn't fail the whole install
        print("[WARNING] Could not create the shortcut ({}).\n"
              "          You can start the program with the Start-{} file in the program folder."
              .format(exc, "Windows.bat" if is_windows else "Mac.command"))

    print("\n" + "=" * 64)
    print("  Installation complete!")
    print("  Start the program with the '{}' icon on your Desktop.".format(APP_NAME))
    print("  Keep this folder where it is - the program runs from it.")
    print("=" * 64)
    return 0


if __name__ == "__main__":
    sys.exit(main())
