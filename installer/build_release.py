#!/usr/bin/env python3
"""
Build the end-user download: the committed code (HEAD) + the active SLEAP model.

Usage:
    python installer/build_release.py v1.0.0
    -> dist/BeeInteractionDetector-v1.0.0.zip

The model folder is gitignored (best_model.h5 is over GitHub's 100 MB file
limit), so it's added from the local disk, from the path in config.json.
Upload the zip as a GitHub Release asset (limit 2 GB per file).
"""

import json
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NAME = "BeeInteractionDetector"


def git(*args):
    return subprocess.run(["git"] + list(args), cwd=str(ROOT), check=True,
                          capture_output=True, text=True).stdout


def verify(zip_path, prefix):
    """Fail if the zip would break on the target OS."""
    problems = []
    with zipfile.ZipFile(str(zip_path)) as z:
        names = set(z.namelist())
        for required in ("Install-Windows.bat", "Install-Mac.command", "HOW_TO_INSTALL.txt",
                         "installer/setup_app.py", "install_requirements.py", "gui.py"):
            if prefix + required not in names:
                problems.append("missing " + required)
        for info in z.infolist():
            if info.filename.endswith(".command"):
                if not (info.external_attr >> 16) & 0o111:
                    problems.append(info.filename + " is not executable")
                if b"\r\n" in z.read(info):
                    problems.append(info.filename + " has CRLF line endings")
            if info.filename.endswith(".bat") and b"\r\n" not in z.read(info):
                problems.append(info.filename + " lacks CRLF line endings")
    return problems


def main():
    version = sys.argv[1] if len(sys.argv) > 1 else "dev"
    prefix = NAME + "/"

    if git("status", "--porcelain", "--untracked-files=no").strip():
        print("[WARNING] You have uncommitted changes - they are NOT included (the zip is built from HEAD).")

    cfg = json.loads((ROOT / "config.json").read_text())
    model_rel = Path(cfg["model_path"])
    if model_rel.is_absolute():
        sys.exit("[ERROR] config.json model_path must be relative to the project to be bundled.")
    model = ROOT / model_rel
    if not model.is_dir():
        sys.exit("[ERROR] Model folder not found: {}".format(model))

    out = ROOT / "dist" / "{}-{}.zip".format(NAME, version)
    out.parent.mkdir(exist_ok=True)
    if out.exists():
        out.unlink()

    # git archive keeps file modes (executable .command files) and applies
    # .gitattributes line endings (CRLF for .bat).
    git("archive", "--format=zip", "--prefix=" + prefix, "-o", str(out), "HEAD")

    with zipfile.ZipFile(str(out), "a", compression=zipfile.ZIP_DEFLATED) as z:
        for f in sorted(model.rglob("*")):
            if f.is_file() and f.name != ".DS_Store":
                z.write(str(f), prefix + f.relative_to(ROOT).as_posix())

    problems = verify(out, prefix)
    if problems:
        sys.exit("[ERROR] The zip has problems:\n  " + "\n  ".join(problems))

    print("[OK] {}  ({:.0f} MB, commit {})".format(
        out, out.stat().st_size / 1e6, git("rev-parse", "--short", "HEAD").strip()))


if __name__ == "__main__":
    main()
