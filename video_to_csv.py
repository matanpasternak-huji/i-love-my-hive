#!/usr/bin/env python3
"""
Video → CSV Pipeline (SLEAP + NAPS)

Stage 1 — SLEAP multi-instance inference : sleap-track  → raw .slp
Stage 2 — NAPS identity correction       : naps-track   → corrected .slp
Stage 3 — SLEAP CSV export               : sleap-convert → .csv

The final CSV has the same structure as labels.v013_infr-naps.csv and can be
fed directly into find_interactions_by_antennation.py.
"""

import platform
import subprocess
import sys
from pathlib import Path

import cv2


def video_frame_count(path: str) -> int:
    """Return the number of frames actually decodable from a video.

    Container metadata (CAP_PROP_FRAME_COUNT) can overstate the real frame
    count for some mp4 encodings, which makes SLEAP/NAPS try to read frames
    that don't exist. Counting by reading through avoids that mismatch.
    """
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        sys.exit(f"[ERROR] Could not open video to count frames: {path}")
    n = 0
    while True:
        ok, _ = cap.read()
        if not ok:
            break
        n += 1
    cap.release()
    return n


def script_dirs() -> list:
    """Directories where this interpreter's console scripts are installed.

    - venv (macOS/Linux): <venv>/bin/          (next to python)
    - venv (Windows):     <venv>\\Scripts\\     (next to python.exe)
    - conda (Windows):    <env>\\python.exe + <env>\\Scripts\\
    """
    exe_dir = Path(sys.executable).parent
    return [d for d in (exe_dir, exe_dir / "Scripts") if d.is_dir()]


def tool(name: str) -> str:
    """Resolve a console script (sleap-track, naps-track, ...) to a full path.

    Prefer the copy installed with the running interpreter, so the pipeline
    works even when the environment isn't activated (e.g. when launched from
    the GUI or an IDE).
    """
    for d in script_dirs():
        for candidate in (d / f"{name}.exe", d / name):
            if candidate.is_file():
                return str(candidate)
    return name

# ==================== CONFIGURATION ====================

INPUT_VIDEO = "Videos/set3_age3_group12_10min.mp4"

# SLEAP multi-instance model
MULTI_INSTANCE_MODEL = "Current Model/260317_163723.multi_instance.n=240"

# Intermediate and final outputs
RAW_SLP_OUTPUT       = "predictions/raw_output.slp"
CORRECTED_SLP_OUTPUT = "4_NAPS/corrected_output.slp"
FINAL_CSV_OUTPUT     = "4_NAPS/final_data.csv"

# NAPS ArUco / tracking parameters
NAPS_TAG_NODE_NAME                   = "tag"
NAPS_ARUCO_MARKER_SET                = "DICT_5X5_50"
NAPS_ARUCO_CROP_SIZE                 = 50
NAPS_ARUCO_ERROR_CORRECTION_RATE     = 0.6
NAPS_ARUCO_ADAPTIVE_THRESH_CONSTANT  = 7
NAPS_ARUCO_THRESH_WIN_SIZE_MAX       = 23
NAPS_ARUCO_THRESH_WIN_SIZE_STEP      = 10
NAPS_ARUCO_THRESH_WIN_SIZE_MIN       = 3
NAPS_HALF_ROLLING_WINDOW_SIZE        = 20

# NAPS frame range. Leave NAPS_END_FRAME = None to auto-detect the video's
# total frame count (recommended). Set an integer only to cap processing.
NAPS_START_FRAME = 0
NAPS_END_FRAME   = None

# =======================================================


def run(description: str, cmd: list) -> None:
    """Run a command, stream its output, and abort the pipeline on failure."""
    print(f"\n{'=' * 70}")
    print(f"  {description}")
    print(f"{'=' * 70}")
    print("Command:", " ".join(str(c) for c in cmd))
    print()

    result = subprocess.run(cmd, text=True)

    if result.returncode != 0:
        print(f"\n[ERROR] Step failed with exit code {result.returncode}.")
        print(f"        Command: {' '.join(str(c) for c in cmd)}")
        sys.exit(result.returncode)

    print(f"\n[OK] {description} completed successfully.")


def main(input_video: str = None, output_dir: str = None, model: str = None) -> str:
    """
    Run the full SLEAP + NAPS pipeline.

    Args:
        input_video: path to the source video (overrides INPUT_VIDEO config)
        output_dir:  directory where all outputs are written (overrides defaults)
        model:       SLEAP model folder (overrides MULTI_INSTANCE_MODEL config)

    Returns:
        Path to the final CSV file.
    """
    video = input_video or INPUT_VIDEO
    model = model or MULTI_INSTANCE_MODEL

    if output_dir:
        out = Path(output_dir)
        raw_slp       = str(out / "raw_output.slp")
        corrected_slp = str(out / "corrected_output.slp")
        final_csv     = str(out / "tracking_data.csv")
    else:
        raw_slp       = RAW_SLP_OUTPUT
        corrected_slp = CORRECTED_SLP_OUTPUT
        final_csv     = FINAL_CSV_OUTPUT

    # ── Pre-flight checks ──────────────────────────────────────────────────────
    if not Path(video).exists():
        sys.exit(f"[ERROR] Input video not found: {video}")
    if not Path(model).exists():
        sys.exit(f"[ERROR] Multi-instance model not found: {model}")

    Path(raw_slp).parent.mkdir(parents=True, exist_ok=True)
    Path(corrected_slp).parent.mkdir(parents=True, exist_ok=True)

    # Some mp4 encodings report more frames in their container metadata than
    # are actually decodable, which makes SLEAP/NAPS try to read frames past
    # the end of the video and crash. Count the real decodable frames once
    # up front and clamp both tools to that range.
    last_frame = video_frame_count(video) - 1
    print(f"  Last valid frame : {last_frame} (auto-detected)")

    print("\nBee Tracking Pipeline: SLEAP + NAPS")
    print(f"  Input video      : {video}")
    print(f"  Model            : {model}")
    print(f"  Raw SLP output   : {raw_slp}")
    print(f"  Corrected SLP    : {corrected_slp}")
    print(f"  Final CSV        : {final_csv}")

    # ── Step 1: SLEAP multi-instance inference ────────────────────────────────
    sleap_track_cmd = [
        tool("sleap-track"),
        video,
        "--model", model,
        "--tracking.tracker", "simple",
        "--frames", f"0-{last_frame}",
        "--output", raw_slp,
    ]
    if platform.system() == "Darwin" and platform.machine() == "arm64":
        # tensorflow-metal's GPU backend crashes on this model's CropAndResize
        # op on Apple Silicon; CPU inference is the reliable path there.
        sleap_track_cmd.append("--cpu")

    # Sub-steps are labelled "Stage" (not "Step") so they don't collide with
    # main.py's top-level "Step N/3" markers, which the GUI parses for progress.
    run("Stage 1/3 — SLEAP multi-instance inference", sleap_track_cmd)

    # ── Step 2: NAPS identity correction ──────────────────────────────────────
    naps_end_frame = NAPS_END_FRAME
    if naps_end_frame is None:
        naps_end_frame = last_frame
        print(f"  NAPS end frame   : {naps_end_frame} (auto-detected)")

    run(
        "Stage 2/3 — NAPS identity correction (ArUco barcode tracking)",
        [
            tool("naps-track"),
            "--slp-path",                             raw_slp,
            "--video-path",                           video,
            "--output-path",                          corrected_slp,
            "--start-frame",                          str(NAPS_START_FRAME),
            "--end-frame",                            str(naps_end_frame),
            "--tag-node-name",                        NAPS_TAG_NODE_NAME,
            "--aruco-marker-set",                     NAPS_ARUCO_MARKER_SET,
            "--aruco-crop-size",                      str(NAPS_ARUCO_CROP_SIZE),
            "--aruco-error-correction-rate",          str(NAPS_ARUCO_ERROR_CORRECTION_RATE),
            "--aruco-adaptive-thresh-constant",       str(NAPS_ARUCO_ADAPTIVE_THRESH_CONSTANT),
            "--aruco-adaptive-thresh-win-size-max",   str(NAPS_ARUCO_THRESH_WIN_SIZE_MAX),
            "--aruco-adaptive-thresh-win-size-step",  str(NAPS_ARUCO_THRESH_WIN_SIZE_STEP),
            "--aruco-adaptive-thresh-win-size-min",   str(NAPS_ARUCO_THRESH_WIN_SIZE_MIN),
            "--half-rolling-window-size",             str(NAPS_HALF_ROLLING_WINDOW_SIZE),
        ],
    )

    # ── Step 3: SLEAP CSV export ───────────────────────────────────────────────
    run(
        "Stage 3/3 — SLEAP CSV export",
        [
            tool("sleap-convert"),
            corrected_slp,
            "--format", "analysis.csv",
            "--output", final_csv,
        ],
    )

    print(f"\n{'=' * 70}")
    print("  Pipeline complete!")
    print(f"  CSV ready for find_interactions_by_antennation.py:")
    print(f"  {final_csv}")
    print(f"{'=' * 70}\n")

    return final_csv


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="SLEAP + NAPS video → CSV pipeline")
    parser.add_argument("--input",      required=True, help="Path to input video")
    parser.add_argument("--output-dir", default=None,  help="Directory for all outputs")
    parser.add_argument("--model",      default=None,
                        help="SLEAP model folder (overrides MULTI_INSTANCE_MODEL)")
    args = parser.parse_args()

    main(input_video=args.input, output_dir=args.output_dir, model=args.model)