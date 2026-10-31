#!/usr/bin/env python3
"""
Install all dependencies and leave OpenCV in the state NAPS needs.

Usage (from the project folder, with the project's environment active):
    python install_requirements.py

Why not just `pip install -r requirements.txt`?
    sleap[pypi] and imgaug install plain `opencv-python`, which has no
    cv2.aruco module, into the same `cv2` folder as the contrib build NAPS
    needs. pip can't remove or replace packages from a requirements file, so
    this script runs the install and then swaps OpenCV back to the contrib
    build, and finally verifies the result. Works the same on Windows and macOS.
"""

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from opencv_check import REQUIRED_OPENCV  # noqa: E402


def run(args, check=True):
    cmd = [sys.executable] + list(args)
    print("\n$ " + " ".join(cmd), flush=True)
    return subprocess.run(cmd, check=check)


def main():
    print(f"Python: {sys.executable}")
    if sys.version_info[:2] != (3, 10):
        print(f"[WARNING] This project requires Python 3.10; you are running "
              f"{sys.version_info.major}.{sys.version_info.minor}.")

    # 1. Everything in requirements.txt
    run(["-m", "pip", "install", "-r", str(HERE / "requirements.txt")])

    # 2. Remove plain OpenCV (no cv2.aruco) ...
    run(["-m", "pip", "uninstall", "-y", "opencv-python"], check=False)

    # 3. ... and rewrite the cv2 folder with the contrib build. --no-deps so
    #    pip doesn't pull anything else in; --force-reinstall because
    #    uninstalling opencv-python deleted files the contrib build shares.
    run(["-m", "pip", "install", "--force-reinstall", "--no-deps", REQUIRED_OPENCV])

    # 4. Verify in a fresh interpreter (this process may have a stale cv2 cached).
    result = run([str(HERE / "opencv_check.py")], check=False)
    if result.returncode != 0:
        print("\n[ERROR] OpenCV is still not usable by NAPS — see the message above.")
        sys.exit(1)

    print("\n[OK] Environment ready. Start the GUI with:  python gui.py")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as exc:
        print(f"\n[ERROR] Command failed with exit code {exc.returncode}.")
        sys.exit(exc.returncode)
