#!/usr/bin/env python3
"""
Bee Interaction Detection Engine — Antennation-Based

Interaction START: full bilateral antennation — all four antenna tips
(both from each bee) within TOUCH_THRESH px for MIN_TOUCH_FRAMES consecutive
frames.

The interaction center is the centroid of the 4 antenna tips and is updated
every frame that antennation continues.

Interaction END:
  Distance exit: either bee's HEAD moves > D_EXIT from the interaction center.

Using the head (rather than the barcode/tag) as the exit point implicitly
captures directional intent: a bee that hasn't turned around must travel the
full D_EXIT distance to exit, while a bee facing away exits sooner because its
head leads the movement.

While either bee is absent from the CSV the exit checks are suspended; a
decision is made only once both bees reappear.

The bee whose head triggered the exit (moved furthest) is the loser.
"""


import csv
import json
from collections import defaultdict
from enum import Enum

import cv2
import numpy as np
import pandas as pd

# ==================== CONFIGURATION ====================
VIDEO_PATH = "Videos/set3_age3_group12_10min.mp4"
CSV_PATH   = "4_NAPS/final_data.csv"
OUTPUT_PATH = "output/1"

# Bee pairs to track — leave empty [] to track all pairs
TRACKED_PAIRS = []

# Antennation touch threshold (pixels).
TOUCH_THRESH = 50

# Minimum consecutive antennation frames to start an interaction.
MIN_TOUCH_FRAMES = 1

# Minimum keypoint confidence score to accept a detection.
SCORE_THRESH = 0.3

# ── Exit condition: distance ───────────────────────────────────────────────────
# End when a bee's HEAD moves beyond this distance from the interaction center.
D_EXIT = 100

# ── Cancellation ──────────────────────────────────────────────────────────────
MAX_INTERACTION_FRAMES = 1500  # 3000 is 100s at 30 fps

# Adaptive exit threshold factor (multiplied by mean head-to-abdomen body length)
D_EXIT_FACTOR = 1

# Output
OUTPUT_JSON  = "interactions_antennation.json"
OUTPUT_CSV   = "interactions_antennation.csv"
OUTPUT_VIDEO = "interactions_antennation_visualized.mp4"

# Visualization
SHOW_LIVE  = True
SAVE_VIDEO = True
# =======================================================


class InteractionState(Enum):
    IDLE        = "idle"
    INTERACTING = "interacting"


# ── CSV / keypoint helpers ─────────────────────────────────────────────────────

def load_csv(csv_path: str):
    """Return (frame_groups dict, sorted list of all track IDs)."""
    df = pd.read_csv(csv_path)
    df = df.replace({None: np.nan})
    frame_groups = {fid: grp for fid, grp in df.groupby("frame_idx")}
    all_ids = sorted(df["track"].dropna().unique().tolist())
    return frame_groups, all_ids


def get_bee_keypoints(frame_groups: dict, bee_id: str, frame_number: int):
    """Return full keypoint dict for bee_id at frame_number, or None."""
    if frame_number not in frame_groups:
        return None
    rows = frame_groups[frame_number]
    bee_rows = rows[rows["track"] == bee_id]
    if bee_rows.empty:
        return None
    r = bee_rows.iloc[0]
    def kp(xk, yk, sk):
        return (r.get(xk, np.nan), r.get(yk, np.nan), r.get(sk, 0))
    return {
        "tag":       kp("tag.x",       "tag.y",       "tag.score"),
        "head":      kp("head.x",      "head.y",      "head.score"),
        "abdomen":   kp("abdomen.x",   "abdomen.y",   "abdomen.score"),
        "ant_R":     kp("ant_R.x",     "ant_R.y",     "ant_R.score"),
        "ant_L":     kp("ant_L.x",     "ant_L.y",     "ant_L.score"),
        "ant_R_end": kp("ant_R_end.x", "ant_R_end.y", "ant_R_end.score"),
        "ant_L_end": kp("ant_L_end.x", "ant_L_end.y", "ant_L_end.score"),
    }


def _valid_pt(triple):
    """Return (x, y) from a keypoint triple if confident, else None."""
    x, y, s = triple
    if np.isnan(x) or np.isnan(y) or s < SCORE_THRESH:
        return None
    return (float(x), float(y))


def body_pos(kp):
    """Best available body position: tag preferred, then head."""
    if kp is None:
        return None
    for key in ("tag", "head"):
        pt = _valid_pt(kp[key])
        if pt is not None:
            return pt
    return None


def antenna_tips(kp):
    """Return ((Rx,Ry), (Lx,Ly)) if both tips are valid, else None."""
    if kp is None:
        return None
    r = _valid_pt(kp["ant_R_end"])
    l = _valid_pt(kp["ant_L_end"])
    if r is None or l is None:
        return None
    return r, l


def pdist(p1, p2) -> float:
    if p1 is None or p2 is None:
        return float("inf")
    return float(np.hypot(p1[0] - p2[0], p1[1] - p2[1]))


def head_pos(kp):
    """Return head position if valid, else None."""
    if kp is None:
        return None
    return _valid_pt(kp["head"])


def check_antennation(kpA, kpB):
    """
    Returns the centroid of the 4 antenna tips if full bilateral antennation
    is detected, else None.

    Each of the 4 tips must be within TOUCH_THRESH of at least one tip from
    the opposing bee.
    """
    tA = antenna_tips(kpA)
    tB = antenna_tips(kpB)
    if tA is None or tB is None:
        return None
    aR, aL = tA
    bR, bL = tB
    if min(pdist(aR, bR), pdist(aR, bL)) > TOUCH_THRESH:
        return None
    if min(pdist(aL, bR), pdist(aL, bL)) > TOUCH_THRESH:
        return None
    if min(pdist(bR, aR), pdist(bR, aL)) > TOUCH_THRESH:
        return None
    if min(pdist(bL, aR), pdist(bL, aL)) > TOUCH_THRESH:
        return None
    cx = (aR[0] + aL[0] + bR[0] + bL[0]) / 4
    cy = (aR[1] + aL[1] + bR[1] + bL[1]) / 4
    return cx, cy


# ── Interaction tracker ────────────────────────────────────────────────────────

class InteractionTracker:
    def __init__(self, touch_thresh, d_exit, max_frames,
                 min_touch_frames, tracked_pairs=None):
        self.touch_thresh      = touch_thresh
        self.d_exit            = d_exit
        self.max_frames        = max_frames
        self.min_touch_frames  = min_touch_frames

        if tracked_pairs:
            self.tracked_pairs = {tuple(sorted(p)) for p in tracked_pairs}
        else:
            self.tracked_pairs = None

        self.pair_states            = {}
        self.completed_interactions = []
        self.position_history       = defaultdict(list)

    def _pair_key(self, a, b):
        return tuple(sorted([a, b]))

    def _fresh_state(self):
        return {
            "state":          InteractionState.IDLE,
            "start_frame":    None,
            "center":         None,
            "last_pos_A":     None,
            "last_pos_B":     None,
            "frame_count":    0,
            "touch_streak":   0,
            "pending_center": None,
        }

    # ── main update ──────────────────────────────────────────────────────────

    def update(self, frame_groups, all_bee_ids, frame_number):
        for bee_id in all_bee_ids:
            kp = get_bee_keypoints(frame_groups, bee_id, frame_number)
            if kp is not None:
                pos = body_pos(kp)
                if pos is not None:
                    self.position_history[bee_id].append((frame_number, pos))

        bee_list = sorted(all_bee_ids)
        for i in range(len(bee_list)):
            for j in range(i + 1, len(bee_list)):
                idA, idB = bee_list[i], bee_list[j]
                pk = self._pair_key(idA, idB)

                if self.tracked_pairs is not None and pk not in self.tracked_pairs:
                    continue

                if pk not in self.pair_states:
                    self.pair_states[pk] = self._fresh_state()
                st = self.pair_states[pk]

                kpA = get_bee_keypoints(frame_groups, idA, frame_number)
                kpB = get_bee_keypoints(frame_groups, idB, frame_number)
                posA = body_pos(kpA)
                posB = body_pos(kpB)

                if posA:
                    st["last_pos_A"] = posA
                if posB:
                    st["last_pos_B"] = posB

                center_candidate = check_antennation(kpA, kpB) if (kpA and kpB) else None

                self._step(st, idA, idB, frame_number, kpA, kpB, posA, posB, center_candidate)

    def _step(self, st, idA, idB, frame_number, kpA, kpB, posA, posB, center_candidate):
        if st["state"] == InteractionState.IDLE:
            if center_candidate is not None:
                st["touch_streak"]  += 1
                st["pending_center"] = center_candidate
                if st["touch_streak"] >= self.min_touch_frames:
                    st["state"]          = InteractionState.INTERACTING
                    st["start_frame"]    = frame_number
                    st["center"]         = st["pending_center"]
                    st["last_pos_A"]     = posA or st["last_pos_A"]
                    st["last_pos_B"]     = posB or st["last_pos_B"]
                    st["frame_count"]    = st["touch_streak"]
                    st["touch_streak"]   = 0
                    st["pending_center"] = None
            else:
                st["touch_streak"]   = 0
                st["pending_center"] = None

        elif st["state"] == InteractionState.INTERACTING:
            st["frame_count"] += 1

            # Update center while antennation continues
            if center_candidate is not None:
                st["center"] = center_candidate

            # ── Feature 1: suspend exit checks while either head is absent ──────
            headA = head_pos(kpA)
            headB = head_pos(kpB)
            if headA is None or headB is None:
                # No decision until both heads are visible again
                if st["frame_count"] > self.max_frames:
                    self._record_canceled(st, idA, idB, frame_number, float("inf"), float("inf"))
                    self._reset(st)
                return

            center = st["center"]
            dA = pdist(headA, center)
            dB = pdist(headB, center)

            # ── Exit condition: head distance ─────────────────────────────────
            loser, reason = None, None
            if dA > self.d_exit and dB > self.d_exit:
                loser  = idA if dA >= dB else idB
                reason = "distance_exit"
            elif dA > self.d_exit:
                loser, reason = idA, "distance_exit"
            elif dB > self.d_exit:
                loser, reason = idB, "distance_exit"

            if loser is not None:
                self._end(st, idA, idB, frame_number, loser, reason, dA, dB)
                self._reset(st)
                return

            # ── Cancellation ──────────────────────────────────────────────────
            if st["frame_count"] > self.max_frames:
                self._record_canceled(st, idA, idB, frame_number, dA, dB)
                self._reset(st)

    def _end(self, st, idA, idB, frame_number, loser_id, reason, dA, dB):
        winner_id = idB if loser_id == idA else idA
        self.completed_interactions.append({
            "bee1_id":            idA,
            "bee2_id":            idB,
            "entrance_frame":     st["start_frame"],
            "exit_frame":         frame_number,
            "duration_frames":    st["frame_count"],
            "winner":             winner_id,
            "loser":              loser_id,
            "dist_from_center_A": float(dA),
            "dist_from_center_B": float(dB),
            "reason":             reason,
        })

    def _record_canceled(self, st, idA, idB, frame_number, dA, dB):
        self.completed_interactions.append({
            "bee1_id":            idA,
            "bee2_id":            idB,
            "entrance_frame":     st["start_frame"],
            "exit_frame":         frame_number,
            "duration_frames":    st["frame_count"],
            "winner":             "canceled",
            "loser":              "canceled",
            "dist_from_center_A": float(dA),
            "dist_from_center_B": float(dB),
            "reason":             "max_duration_exceeded",
        })

    def _reset(self, st):
        st["state"]          = InteractionState.IDLE
        st["start_frame"]    = None
        st["center"]         = None
        st["frame_count"]    = 0
        st["touch_streak"]   = 0
        st["pending_center"] = None

    def get_summary(self):
        win_counts = defaultdict(int)
        for i in self.completed_interactions:
            w = i.get("winner")
            if w and w != "canceled":
                win_counts[w] += 1
        return {
            "total_interactions":     len(self.completed_interactions),
            "completed_interactions": sum(1 for i in self.completed_interactions if i.get("winner") != "canceled"),
            "canceled_interactions":  sum(1 for i in self.completed_interactions if i.get("winner") == "canceled"),
            "win_counts":             dict(win_counts),
            "interactions":           self.completed_interactions,
        }


# ── Adaptive threshold computation ────────────────────────────────────────────

def compute_exit_threshold(frame_groups):
    """
    Estimate D_EXIT from the first 500 annotated frames.

    Measures the head-to-abdomen distance for every bee in every frame,
    takes the mean, then applies the configured scaling factor:
      D_EXIT = mean_body_length × D_EXIT_FACTOR

    Falls back to the hardcoded config value if measurement fails.
    """
    distances = []
    for frame_idx in sorted(frame_groups.keys())[:500]:
        for _, row in frame_groups[frame_idx].iterrows():
            hx = row.get("head.x",    float("nan"))
            hy = row.get("head.y",    float("nan"))
            ax = row.get("abdomen.x", float("nan"))
            ay = row.get("abdomen.y", float("nan"))
            if any(np.isnan(v) for v in (hx, hy, ax, ay)):
                continue
            d = float(np.hypot(hx - ax, hy - ay))
            if d > 10:
                distances.append(d)

    if not distances:
        print("[WARN] Could not measure bee size — using hardcoded threshold.")
        return D_EXIT

    avg = float(np.mean(distances))
    d_exit = avg * D_EXIT_FACTOR
    print(f"  Avg bee body length : {avg:.1f} px  (n={len(distances)}, frames=first 500)")
    print(f"  D_EXIT              = {avg:.1f} × {D_EXIT_FACTOR} = {d_exit:.1f} px")
    return d_exit


# ── Processing pass ────────────────────────────────────────────────────────────

def process_video(video_path, csv_path):
    print("\n" + "=" * 70)
    print("Bee Interaction Detection — Antennation-Based")
    print("=" * 70)
    print(f"\nVideo : {video_path}")
    print(f"CSV   : {csv_path}")
    print(f"\nSettings:")
    print(f"  TOUCH_THRESH       : {TOUCH_THRESH} px")
    print(f"  MIN_TOUCH_FRAMES   : {MIN_TOUCH_FRAMES}")
    print(f"  D_EXIT             : (adaptive — computed from video)")
    print(f"  MAX_INTERACTION_F  : {MAX_INTERACTION_FRAMES}")
    print(f"  TRACKED_PAIRS      : {TRACKED_PAIRS or 'ALL'}")

    frame_groups, all_ids = load_csv(csv_path)
    print(f"\nLoaded CSV: {len(all_ids)} tracks, {len(frame_groups)} annotated frames")

    print("\nComputing adaptive exit threshold from first 500 frames...")
    d_exit = compute_exit_threshold(frame_groups)

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {video_path}")
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    print(f"Video: {total_frames} frames")

    tracker = InteractionTracker(
        TOUCH_THRESH, d_exit, MAX_INTERACTION_FRAMES,
        MIN_TOUCH_FRAMES, TRACKED_PAIRS or None,
    )

    print("\nProcessing frames...\n")
    max_frame = max(list(frame_groups.keys())) if frame_groups else 0
    for frame_number in range(1, max_frame + 1):
        tracker.update(frame_groups, all_ids, frame_number)
        if frame_number % 500 == 0:
            active = sum(
                1 for s in tracker.pair_states.values()
                if s["state"] == InteractionState.INTERACTING
            )
            print(f"  Frame {frame_number}/{max_frame} | "
                  f"Active: {active} | "
                  f"Completed: {len(tracker.completed_interactions)}")

    print("\nProcessing complete!")
    return tracker.get_summary(), tracker


# ── Visualization helpers ──────────────────────────────────────────────────────

def _draw_arrow(frame, p1, p2, color, thickness=2, tip_length=0.3):
    """Draw an arrowed line from p1 to p2 if both are valid."""
    if p1 is None or p2 is None:
        return
    cv2.arrowedLine(frame,
                    (int(p1[0]), int(p1[1])),
                    (int(p2[0]), int(p2[1])),
                    color, thickness, cv2.LINE_AA, tipLength=tip_length)


def _draw_seg(frame, p1, p2, color, thickness=1):
    if p1 is None or p2 is None:
        return
    cv2.line(frame,
             (int(p1[0]), int(p1[1])),
             (int(p2[0]), int(p2[1])),
             color, thickness, cv2.LINE_AA)


def _dot(frame, pt, color, r=4):
    if pt is None:
        return
    cv2.circle(frame, (int(pt[0]), int(pt[1])), r, color, -1, cv2.LINE_AA)
    cv2.circle(frame, (int(pt[0]), int(pt[1])), r, (0, 0, 0), 1, cv2.LINE_AA)


def draw_skeleton(frame, kp, axis_color):
    """
    Draw full skeleton for one bee.
      axis_color — color of the abdomen→head body-axis arrow (reflects
                   facing-toward/away state during an interaction).
    """
    if kp is None:
        return

    tag     = _valid_pt(kp["tag"])
    head    = _valid_pt(kp["head"])
    abdomen = _valid_pt(kp["abdomen"])
    ant_r   = _valid_pt(kp["ant_R"])
    ant_l   = _valid_pt(kp["ant_L"])
    ant_re  = _valid_pt(kp["ant_R_end"])
    ant_le  = _valid_pt(kp["ant_L_end"])

    # Body axis: abdomen ── tag ── head  (arrow points toward head)
    _draw_seg(frame, abdomen, tag,  axis_color, 2)
    _draw_arrow(frame, tag, head,   axis_color, 2, 0.35)

    # Antennae: head → base → tip
    _draw_seg(frame, head, ant_r, (160, 220, 160), 1)
    _draw_seg(frame, head, ant_l, (160, 220, 160), 1)
    _draw_seg(frame, ant_r, ant_re, (0, 220, 120), 1)
    _draw_seg(frame, ant_l, ant_le, (0, 220, 120), 1)

    # Keypoint dots (drawn on top of lines)
    _dot(frame, abdomen, (50,  100, 220), 5)   # blue — abdomen
    _dot(frame, tag,     (255, 255, 255), 5)   # white — tag
    _dot(frame, head,    (255, 220,  50), 5)   # yellow — head
    _dot(frame, ant_r,   (0,  200, 100), 3)    # green — antenna bases
    _dot(frame, ant_l,   (0,  200, 100), 3)
    _dot(frame, ant_re,  (0,  230, 255), 4)    # cyan — antenna tips
    _dot(frame, ant_le,  (0,  230, 255), 4)


# ── Visualization pass ─────────────────────────────────────────────────────────

def visualize(video_path, csv_path, show=True, save=True, output_video_path=None):
    print("\n" + "=" * 70)
    print("Visualizing Antennation Interactions")
    print("=" * 70)

    frame_groups, all_ids = load_csv(csv_path)

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {video_path}")

    fps          = int(cap.get(cv2.CAP_PROP_FPS)) or 30
    width        = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height       = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    out = None
    if save:
        out_path = output_video_path or OUTPUT_VIDEO
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        out    = cv2.VideoWriter(out_path, fourcc, fps, (width, height))
        print(f"Output: {out_path}")

    d_exit = compute_exit_threshold(frame_groups)

    viz_tracker = InteractionTracker(
        TOUCH_THRESH, d_exit, MAX_INTERACTION_FRAMES,
        MIN_TOUCH_FRAMES, TRACKED_PAIRS or None,
    )

    C = {
        "interacting":   (0,   255,   0),
        "touch":         (0,   230, 255),
        "center":        (255,   0, 255),
        "exit_ring":     (0,    80, 255),   # D_EXIT ring
        "interacting_axis": (0, 255, 100),  # body axis during interaction
        "neutral_axis":  (180, 180, 180),   # not in interaction
        "event_start":   (0,   255,   0),
        "event_end":     (255, 255,   0),
        "event_cancel":  (0,    80, 255),
    }

    recent_events = []
    shown_keys    = set()
    frame_number  = 0

    print("\nVisualizing... (press Q to quit)\n")

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frame_number += 1

        old_states = {pk: si["state"] for pk, si in viz_tracker.pair_states.items()}
        viz_tracker.update(frame_groups, all_ids, frame_number)

        # ── State-change events ───────────────────────────────────────────────
        for pk, si in viz_tracker.pair_states.items():
            if old_states.get(pk, InteractionState.IDLE) != si["state"]:
                if si["state"] == InteractionState.INTERACTING:
                    a, b = pk
                    recent_events.append((frame_number, f"START: {a} ↔ {b}", C["event_start"]))

        for ix in viz_tracker.completed_interactions:
            ik = (ix["bee1_id"], ix["bee2_id"], ix["exit_frame"])
            if ix["exit_frame"] == frame_number and ik not in shown_keys:
                shown_keys.add(ik)
                a, b, w = ix["bee1_id"], ix["bee2_id"], ix["winner"]
                reason   = ix.get("reason", "")
                if w == "canceled":
                    recent_events.append((frame_number, f"CANCELED: {a} ↔ {b}", C["event_cancel"]))
                else:
                    recent_events.append((frame_number,
                                          f"END: {a} ↔ {b}  winner={w}",
                                          C["event_end"]))

        recent_events = [e for e in recent_events if frame_number - e[0] < 90]

        # ── Per-bee keypoints for this frame ──────────────────────────────────
        bee_kp  = {}   # bee_id -> kp dict
        bee_pos = {}   # bee_id -> (x, y)
        for bee_id in all_ids:
            kp = get_bee_keypoints(frame_groups, bee_id, frame_number)
            if kp is not None:
                bee_kp[bee_id]  = kp
                pos = body_pos(kp)
                if pos:
                    bee_pos[bee_id] = pos

        # ── Determine axis color per bee (interaction context) ────────────────
        # Default: neutral gray
        axis_colors = {bee_id: C["neutral_axis"] for bee_id in all_ids}

        for pk, si in viz_tracker.pair_states.items():
            if si["state"] != InteractionState.INTERACTING:
                continue
            idA, idB = pk
            for bee_id in (idA, idB):
                axis_colors[bee_id] = C["interacting_axis"]

        # ── Draw skeletons ────────────────────────────────────────────────────
        for bee_id in all_ids:
            draw_skeleton(frame, bee_kp.get(bee_id), axis_colors[bee_id])
            # Label
            pos = bee_pos.get(bee_id)
            if pos:
                label = bee_id.replace("ArUcoTag#", "#")
                cv2.putText(frame, label, (int(pos[0]) + 9, int(pos[1]) - 8),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 0), 3, cv2.LINE_AA)
                cv2.putText(frame, label, (int(pos[0]) + 9, int(pos[1]) - 8),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1, cv2.LINE_AA)

        # ── Draw interaction overlays ─────────────────────────────────────────
        for pk, si in viz_tracker.pair_states.items():
            idA, idB = pk
            posA = bee_pos.get(idA)
            posB = bee_pos.get(idB)

            if si["state"] == InteractionState.INTERACTING:
                # Line between bee bodies
                if posA and posB:
                    _draw_seg(frame, posA, posB, C["interacting"], 2)

                center = si["center"]
                if center:
                    cx, cy = int(center[0]), int(center[1])

                    # Interaction center dot
                    cv2.circle(frame, (cx, cy), 8, C["center"], -1, cv2.LINE_AA)
                    cv2.circle(frame, (cx, cy), 9, (0, 0, 0), 1, cv2.LINE_AA)

                    # D_EXIT ring (head-distance exit boundary)
                    cv2.circle(frame, (cx, cy), int(d_exit), C["exit_ring"], 1, cv2.LINE_AA)

                    # Frame counter
                    headA_viz = head_pos(bee_kp.get(idA))
                    headB_viz = head_pos(bee_kp.get(idB))
                    suspended = (headA_viz is None or headB_viz is None)
                    count_txt = f"{si['frame_count']}f" + (" [wait]" if suspended else "")
                    cv2.putText(frame, count_txt, (cx + 10, cy),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 0), 3, cv2.LINE_AA)
                    cv2.putText(frame, count_txt, (cx + 10, cy),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.4, C["center"], 1, cv2.LINE_AA)

                # Highlight active antenna tips in cyan when touching
                kpA = bee_kp.get(idA)
                kpB = bee_kp.get(idB)
                if kpA and kpB and check_antennation(kpA, kpB) is not None:
                    for tip in list(antenna_tips(kpA) or []) + list(antenna_tips(kpB) or []):
                        cv2.circle(frame, (int(tip[0]), int(tip[1])), 6, C["touch"], -1, cv2.LINE_AA)

            elif si["touch_streak"] > 0:
                # Pre-start pending antennation
                if posA and posB:
                    _draw_seg(frame, posA, posB, C["touch"], 1)

        # ── HUD ──────────────────────────────────────────────────────────────
        active = sum(1 for s in viz_tracker.pair_states.values()
                     if s["state"] == InteractionState.INTERACTING)
        hud = (f"Frame {frame_number}/{total_frames}  "
               f"Active: {active}  "
               f"Completed: {len(viz_tracker.completed_interactions)}")
        cv2.putText(frame, hud, (10, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 3, cv2.LINE_AA)
        cv2.putText(frame, hud, (10, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA)

        y = 50
        for _, msg, color in recent_events[-5:]:
            cv2.putText(frame, msg, (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (0, 0, 0), 3, cv2.LINE_AA)
            cv2.putText(frame, msg, (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.52, color,       1, cv2.LINE_AA)
            y += 26

        # Legend
        ly = height - 110
        cv2.rectangle(frame, (8, ly - 5), (310, height - 8), (0, 0, 0), -1)
        legend = [
            ("● blue=abdomen  white=tag  yellow=head", (200, 200, 200)),
            ("● cyan=antenna tips  green=antenna segs", (200, 200, 200)),
            ("→ green axis: interacting  gray: idle", (200, 200, 200)),
            ("● magenta: interaction center", C["center"]),
            (f"○ red ring: D_EXIT (head)={d_exit:.0f}px", C["exit_ring"]),
        ]
        for k, (txt, col) in enumerate(legend):
            cv2.putText(frame, txt, (14, ly + 14 + k * 18),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.35, col, 1, cv2.LINE_AA)

        if out:
            out.write(frame)
        if show:
            cv2.imshow("Antennation Interactions", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                print("\nStopped by user.")
                break

        if frame_number % 500 == 0:
            print(f"  Frame {frame_number}/{total_frames}...")

    cap.release()
    if out:
        out.release()
    cv2.destroyAllWindows()
    print("\nVisualization complete!")


# ── Save results ───────────────────────────────────────────────────────────────

def save_results(summary, json_path, csv_path_out):
    with open(json_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nJSON saved : {json_path}")

    fieldnames = [
        "bee1_id", "bee2_id", "entrance_frame", "exit_frame",
        "duration_frames", "winner", "loser",
        "dist_from_center_A", "dist_from_center_B", "reason",
    ]
    with open(csv_path_out, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in summary["interactions"]:
            writer.writerow(row)
    print(f"CSV saved  : {csv_path_out}")

    print("\n" + "=" * 70)
    print("Summary")
    print("=" * 70)
    print(f"Total     : {summary['total_interactions']}")
    print(f"Completed : {summary['completed_interactions']}")
    print(f"Canceled  : {summary['canceled_interactions']}")
    print("\nWin counts:")
    for bee_id, wins in sorted(summary["win_counts"].items()):
        print(f"  {bee_id}: {wins} wins")

    pair_map = defaultdict(list)
    for i in summary["interactions"]:
        pk = tuple(sorted([i["bee1_id"], i["bee2_id"]]))
        pair_map[pk].append(i)
    print("\nPer-pair breakdown:")
    for (a, b), rows in sorted(pair_map.items()):
        done = [r for r in rows if r["winner"] != "canceled"]
        canc = [r for r in rows if r["winner"] == "canceled"]
        dir_exits  = [r for r in done if r.get("reason") == "direction_exit"]
        dist_exits = [r for r in done if r.get("reason") == "distance_exit"]
        print(f"\n  {a} ↔ {b}")
        print(f"    Total: {len(rows)}  Completed: {len(done)}  Canceled: {len(canc)}")
        print(f"    Distance exits : {len(dist_exits)}")
        print(f"    Direction exits: {len(dir_exits)}")
        print(f"    {a} wins: {sum(1 for r in done if r['winner'] == a)}")
        print(f"    {b} wins: {sum(1 for r in done if r['winner'] == b)}")


# ── Entry point ────────────────────────────────────────────────────────────────

def apply_cli_overrides(args):
    """Apply argparse namespace values to module-level config globals."""
    global TOUCH_THRESH, MIN_TOUCH_FRAMES, D_EXIT_FACTOR, MAX_INTERACTION_FRAMES
    global SHOW_LIVE, SAVE_VIDEO
    if args.touch_thresh is not None:
        TOUCH_THRESH = args.touch_thresh
    if args.min_touch_frames is not None:
        MIN_TOUCH_FRAMES = args.min_touch_frames
    if args.d_exit_factor is not None:
        D_EXIT_FACTOR = args.d_exit_factor
    if args.max_frames is not None:
        MAX_INTERACTION_FRAMES = args.max_frames
    if args.no_show_live:
        SHOW_LIVE = False
    if args.no_save_video:
        SAVE_VIDEO = False


if __name__ == "__main__":
    import argparse
    import sys
    from pathlib import Path

    parser = argparse.ArgumentParser(description="Bee interaction detection via antennation")
    parser.add_argument("--video",      default=VIDEO_PATH, help="Path to input video")
    parser.add_argument("--csv",        default=CSV_PATH,   help="Path to tracking CSV")
    parser.add_argument("--output-dir", default=OUTPUT_PATH,       help="Directory for all outputs")
    parser.add_argument("--touch-thresh",     type=int,   default=None,
                        help="Touch threshold in pixels (overrides TOUCH_THRESH)")
    parser.add_argument("--min-touch-frames", type=int,   default=None,
                        help="Min consecutive touch frames (overrides MIN_TOUCH_FRAMES)")
    parser.add_argument("--d-exit-factor",    type=float, default=None,
                        help="Exit distance factor x avg body length (overrides D_EXIT_FACTOR)")
    parser.add_argument("--max-frames",       type=int,   default=None,
                        help="Max interaction frames before cancel (overrides MAX_INTERACTION_FRAMES)")
    parser.add_argument("--no-show-live",     action="store_true",
                        help="Suppress the live OpenCV visualisation window")
    parser.add_argument("--no-save-video",    action="store_true",
                        help="Skip saving the annotated output video")
    args = parser.parse_args()
    apply_cli_overrides(args)

    video_path = args.video
    csv_path   = args.csv

    if args.output_dir:
        out = Path(args.output_dir)
        out.mkdir(parents=True, exist_ok=True)
        output_json  = str(out / "interactions.json")
        output_csv   = str(out / "interactions.csv")
        output_video = str(out / "interactions_visualized.mp4")
    else:
        output_json  = OUTPUT_JSON
        output_csv   = OUTPUT_CSV
        output_video = OUTPUT_VIDEO

    if not Path(video_path).exists():
        sys.exit(f"Video not found: {video_path}")
    if not Path(csv_path).exists():
        sys.exit(f"CSV not found: {csv_path}")

    summary, tracker = process_video(video_path, csv_path)
    save_results(summary, output_json, output_csv)

    print("\n" + "=" * 70)
    print("Generating Visualization")
    print("=" * 70)
    visualize(video_path, csv_path, show=SHOW_LIVE, save=SAVE_VIDEO,
              output_video_path=output_video)