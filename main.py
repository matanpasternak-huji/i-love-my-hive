#!/usr/bin/env python3
"""
main.py — Bee tracking & interaction detection pipeline

Usage:
    python main.py --input <video.mp4> --output <output_dir>

Creates a timestamped run folder inside <output_dir>, then runs:
  1. video_to_csv.py                     — SLEAP inference + NAPS identity correction → CSV
  2. find_interactions_by_antennation.py — interaction detection → JSON/CSV/video
  3. split_to_groups.py                  — split interactions by petri dish group
"""

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def run_step(description: str, cmd: list) -> None:
    """Run a subprocess, streaming its output live. Abort on failure."""
    sep = "=" * 70
    print(f"\n{sep}")
    print(f"  {description}")
    print(f"{sep}")
    print("Command:", " ".join(str(c) for c in cmd))
    print()

    result = subprocess.run(cmd)

    if result.returncode != 0:
        print(f"\n[ERROR] {description} failed (exit {result.returncode}).")
        sys.exit(result.returncode)

    print(f"\n[OK] {description} completed.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="End-to-end bee tracking and interaction detection pipeline"
    )
    parser.add_argument("--input",  required=True, help="Path to input video")
    parser.add_argument("--output", required=True, help="Root output directory")
    args = parser.parse_args()

    video_path = Path(args.input).resolve()
    if not video_path.exists():
        sys.exit(f"[ERROR] Input video not found: {video_path}")

    # ── Create timestamped run folder ──────────────────────────────────────────
    timestamp  = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir    = Path(args.output).resolve() / timestamp
    run_dir.mkdir(parents=True, exist_ok=True)

    print(f"\nRun folder : {run_dir}")
    print(f"Input video: {video_path}")

    # ── Step 1: SLEAP + NAPS → tracking CSV ───────────────────────────────────
    run_step(
        "Step 1/3 — SLEAP inference + NAPS identity correction",
        [
            sys.executable, "video_to_csv.py",
            "--input",      str(video_path),
            "--output-dir", str(run_dir),
        ],
    )

    tracking_csv = run_dir / "tracking_data.csv"
    if not tracking_csv.exists():
        sys.exit(f"[ERROR] Expected tracking CSV not found: {tracking_csv}")

    # ── Step 2: interaction detection ─────────────────────────────────────────
    run_step(
        "Step 2/3 — Interaction detection (antennation-based)",
        [
            sys.executable, "find_interactions_by_antennation.py",
            "--video",      str(video_path),
            "--csv",        str(tracking_csv),
            "--output-dir", str(run_dir),
        ],
    )

    interactions_csv = run_dir / "interactions.csv"
    if not interactions_csv.exists():
        sys.exit(f"[ERROR] Expected interactions CSV not found: {interactions_csv}")

    # ── Step 3: split by group ─────────────────────────────────────────────────
    run_step(
        "Step 3/3 — Split interactions by bee group",
        [
            sys.executable, "split_to_groups.py",
            "--input",      str(interactions_csv),
            "--output-dir", str(run_dir),
        ],
    )

    # ── Done ───────────────────────────────────────────────────────────────────
    print(f"\n{'=' * 70}")
    print("  Pipeline complete!")
    print(f"  All outputs in: {run_dir}")
    print(f"    tracking_data.csv")
    print(f"    interactions.json")
    print(f"    interactions.csv")
    print(f"    interactions_visualized.mp4")
    print(f"    group_*.csv  (one per petri dish)")
    print(f"{'=' * 70}\n")


if __name__ == "__main__":
    main()