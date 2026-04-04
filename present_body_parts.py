#!/usr/bin/env python3
"""
present_body_parts.py

Overlays SLEAP body-part predictions onto a video.

Reads  : 4_NAPS/final_data.csv  (one row per bee per frame)
         Videos/set3_age3_group12_10min.mp4
Writes : Videos/set3_age3_group12_10min_annotated.mp4
"""

import cv2
import pandas as pd
import numpy as np
from pathlib import Path

# ==================== CONFIGURATION ====================

INPUT_CSV    = "4_NAPS/final_data.csv"
INPUT_VIDEO  = "Videos/set3_age3_group12_10min.mp4"
OUTPUT_VIDEO = "Videos/set3_age3_group12_10min_annotated.mp4"

NODE_RADIUS      = 6
LABEL_FONT_SCALE = 0.35
SHOW_NODE_NAMES  = False   # draw node name next to each dot
SHOW_TRACK_LABEL = True   # draw bee ID near the head node

# Skeleton edges: pairs of node names to connect with a line
SKELETON = [
    ("head", "abdomen"),
    ("head", "ant_R"),
    ("head", "ant_L"),
    ("ant_R", "ant_R_end"),
    ("ant_L", "ant_L_end"),
    ("head", "tag"),
]

# =======================================================

_PALETTE = [
    (255,  80,  80),
    ( 80, 255,  80),
    ( 80,  80, 255),
    (255, 255,  80),
    (255,  80, 255),
    ( 80, 255, 255),
    (255, 160,   0),
    (160,   0, 255),
    (  0, 200, 160),
    (200, 200,  60),
]


def color_for_track(track_name: str, track_list: list) -> tuple:
    idx = track_list.index(track_name) if track_name in track_list else 0
    return _PALETTE[idx % len(_PALETTE)]


def parse_nodes(columns: list) -> list:
    """Return unique node names detected in the CSV columns (preserving order)."""
    nodes = []
    seen = set()
    for col in columns:
        if col.endswith(".x"):
            node = col[:-2]
            if node not in seen:
                nodes.append(node)
                seen.add(node)
    return nodes


def draw_frame(frame: np.ndarray, rows: pd.DataFrame,
               nodes: list, tracks: list) -> np.ndarray:
    """Annotate a single frame with all bee poses."""
    out = frame.copy()

    for _, row in rows.iterrows():
        track = row["track"]
        color = color_for_track(track, tracks)

        # Collect valid (x, y) per node
        coords = {}
        for node in nodes:
            x = row.get(f"{node}.x", float("nan"))
            y = row.get(f"{node}.y", float("nan"))
            if pd.notna(x) and pd.notna(y) and x > 0 and y > 0:
                coords[node] = (int(round(x)), int(round(y)))

        # Draw skeleton edges first (so dots appear on top)
        for n1, n2 in SKELETON:
            if n1 in coords and n2 in coords:
                cv2.line(out, coords[n1], coords[n2], color, 1, cv2.LINE_AA)

        # Draw node dots
        for node, (x, y) in coords.items():
            cv2.circle(out, (x, y), NODE_RADIUS, color, -1, cv2.LINE_AA)
            if SHOW_NODE_NAMES:
                cv2.putText(out, node, (x + NODE_RADIUS + 1, y + 3),
                            cv2.FONT_HERSHEY_SIMPLEX, LABEL_FONT_SCALE,
                            color, 1, cv2.LINE_AA)

        # Draw track label near head (or first available node)
        if SHOW_TRACK_LABEL:
            anchor = coords.get("head") or (next(iter(coords.values())) if coords else None)
            if anchor:
                cv2.putText(out, str(track), (anchor[0] + 6, anchor[1] - 8),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45,
                            color, 1, cv2.LINE_AA)

    return out


def main() -> None:
    # ── Load CSV ───────────────────────────────────────────────────────────────
    csv_path = Path(INPUT_CSV)
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV not found: {INPUT_CSV}")

    df = pd.read_csv(csv_path)
    nodes  = parse_nodes(df.columns.tolist())
    tracks = sorted(df["track"].dropna().unique().tolist())
    frames_in_csv = set(df["frame_idx"].unique())

    print(f"CSV loaded: {len(df)} rows | {len(tracks)} tracks | {len(nodes)} nodes")
    print(f"Nodes : {nodes}")
    print(f"Tracks: {tracks}")

    # Pre-group by frame for O(1) lookup
    grouped = df.groupby("frame_idx")

    # ── Open video ─────────────────────────────────────────────────────────────
    cap = cv2.VideoCapture(INPUT_VIDEO)
    if not cap.isOpened():
        raise FileNotFoundError(f"Video not found: {INPUT_VIDEO}")

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps    = cap.get(cv2.CAP_PROP_FPS)
    width  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"Video : {total_frames} frames @ {fps:.1f} fps  |  {width}x{height}")

    # ── Set up writer ──────────────────────────────────────────────────────────
    Path(OUTPUT_VIDEO).parent.mkdir(parents=True, exist_ok=True)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(OUTPUT_VIDEO, fourcc, fps, (width, height))

    # ── Process frame by frame ─────────────────────────────────────────────────
    frame_idx = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if frame_idx in frames_in_csv:
            frame = draw_frame(frame, grouped.get_group(frame_idx), nodes, tracks)

        writer.write(frame)

        if frame_idx % 500 == 0:
            pct = 100 * frame_idx / total_frames if total_frames > 0 else 0
            print(f"  Frame {frame_idx}/{total_frames} ({pct:.1f}%)")

        frame_idx += 1

    cap.release()
    writer.release()
    print(f"\nDone. Annotated video saved to: {OUTPUT_VIDEO}")


if __name__ == "__main__":
    main()