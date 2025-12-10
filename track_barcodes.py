#!/usr/bin/env python3
"""
ArUco Marker-Based Bee Tracking (5x5)

This script detects and tracks bees by reading ArUco markers (5x5) on their backs.
Each marker uniquely identifies a bee, making tracking more reliable than
visual features alone.
"""

import cv2
import numpy as np

# ==================== CONFIGURATION ====================
VIDEO_PATH = "group34_10min.mp4"
OUTPUT_PATH = "group34_barcode_track.mp4"

# ArUco detection settings
ARUCO_DICT = cv2.aruco.DICT_5X5_100  # 5x5 ArUco markers, 100 unique IDs
MIN_MARKER_PERIMETER = 10  # Minimum marker size (pixels) - lowered for small markers
MAX_MARKER_PERIMETER = 4000  # Maximum marker size (pixels)
USE_MULTISCALE = True  # Try multiple scales for better small marker detection
SCALES = [1.0, 1.5, 2.0, 3.0]  # Scales to try (1.0 = original, 2.0 = 2x zoom)

# Tracking settings
MAX_FRAMES_MISSING = 30  # Keep track alive if marker not detected for N frames

# Visualization
SHOW_LIVE = True
SAVE_VIDEO = True
EXPAND_BOX = 50  # Pixels to expand marker box (to show more of the bee)

# Colors for different bees (will cycle through these)
COLORS = [
    (255, 0, 0),  # Blue
    (0, 255, 0),  # Green
    (0, 0, 255),  # Red
    (255, 255, 0),  # Cyan
    (255, 0, 255),  # Magenta
    (0, 255, 255),  # Yellow
    (128, 255, 0),  # Spring Green
    (255, 128, 0),  # Orange
    (128, 0, 255),  # Purple
    (0, 128, 255),  # Light Blue
]
# =======================================================


class BarcodeTracker:
    """Track bees by their ArUco marker IDs."""

    def __init__(self, max_frames_missing=30):
        self.tracks = {}  # marker_id -> track_info
        self.max_frames_missing = max_frames_missing
        self.color_map = {}  # marker_id -> color
        self.next_color_idx = 0

    def get_color(self, marker_id):
        """Get consistent color for a marker ID."""
        if marker_id not in self.color_map:
            self.color_map[marker_id] = COLORS[self.next_color_idx % len(COLORS)]
            self.next_color_idx += 1
        return self.color_map[marker_id]

    def update(self, detections, frame_number):
        """
        Update tracks with new detections.

        Args:
            detections: List of (marker_id, corners, center, bbox)
            frame_number: Current frame number

        Returns:
            List of active tracks
        """
        # Update existing tracks or create new ones
        detected_ids = set()

        for marker_id, corners, center, bbox in detections:
            detected_ids.add(marker_id)

            if marker_id in self.tracks:
                # Update existing track
                self.tracks[marker_id]["corners"] = corners
                self.tracks[marker_id]["center"] = center
                self.tracks[marker_id]["bbox"] = bbox
                self.tracks[marker_id]["last_seen"] = frame_number
                self.tracks[marker_id]["detection_count"] += 1
            else:
                # Create new track
                self.tracks[marker_id] = {
                    "corners": corners,
                    "center": center,
                    "bbox": bbox,
                    "first_seen": frame_number,
                    "last_seen": frame_number,
                    "detection_count": 1,
                    "color": self.get_color(marker_id),
                }

        # Age out old tracks
        to_remove = []
        for marker_id, track in self.tracks.items():
            frames_missing = frame_number - track["last_seen"]
            if frames_missing > self.max_frames_missing:
                to_remove.append(marker_id)

        for marker_id in to_remove:
            del self.tracks[marker_id]

        # Return active tracks
        active_tracks = []
        for marker_id, track in self.tracks.items():
            active_tracks.append((marker_id, track))

        return active_tracks


def detect_aruco_markers(frame, aruco_dict, parameters):
    """
    Detect ArUco markers in a frame with multi-scale detection.

    Returns:
        List of (marker_id, corners, center, bbox)
    """
    all_detections = {}  # marker_id -> (corners, center, bbox, scale)

    # Try different scales if enabled
    scales_to_try = SCALES if USE_MULTISCALE else [1.0]

    for scale in scales_to_try:
        # Resize frame if needed
        if scale != 1.0:
            new_width = int(frame.shape[1] * scale)
            new_height = int(frame.shape[0] * scale)
            scaled_frame = cv2.resize(
                frame, (new_width, new_height), interpolation=cv2.INTER_CUBIC
            )
        else:
            scaled_frame = frame

        # Detect markers
        corners, ids, rejected = cv2.aruco.detectMarkers(
            scaled_frame, aruco_dict, parameters=parameters
        )

        if ids is not None:
            for i, marker_id in enumerate(ids.flatten()):
                marker_id = int(marker_id)

                # Get corner points
                corner_points = corners[i][0].copy()

                # Scale coordinates back to original frame size
                if scale != 1.0:
                    corner_points = corner_points / scale

                # Calculate center in original frame coordinates
                center_x = int(np.mean(corner_points[:, 0]))
                center_y = int(np.mean(corner_points[:, 1]))
                center = (center_x, center_y)

                # Calculate bounding box from corners
                x_coords = corner_points[:, 0]
                y_coords = corner_points[:, 1]
                x_min = int(np.min(x_coords))
                y_min = int(np.min(y_coords))
                x_max = int(np.max(x_coords))
                y_max = int(np.max(y_coords))
                bbox = (x_min, y_min, x_max - x_min, y_max - y_min)

                # Only keep the detection if it's new or larger than previous
                if marker_id not in all_detections:
                    all_detections[marker_id] = (corner_points, center, bbox, scale)
                else:
                    # Keep the detection from the scale that found it largest/clearest
                    existing_corners = all_detections[marker_id][0]
                    existing_size = np.linalg.norm(
                        existing_corners[0] - existing_corners[2]
                    )
                    new_size = np.linalg.norm(corner_points[0] - corner_points[2])
                    if new_size > existing_size:
                        all_detections[marker_id] = (corner_points, center, bbox, scale)

    # Convert to list format
    detections = [
        (mid, corners, center, bbox)
        for mid, (corners, center, bbox, scale) in all_detections.items()
    ]

    return detections


def expand_bbox(bbox, expand_pixels, frame_shape):
    """Expand bounding box by N pixels (to show more of the bee)."""
    x, y, w, h = bbox
    height, width = frame_shape[:2]

    x = max(0, x - expand_pixels)
    y = max(0, y - expand_pixels)
    w = min(width - x, w + 2 * expand_pixels)
    h = min(height - y, h + 2 * expand_pixels)

    return (x, y, w, h)


def draw_barcode_info(frame, marker_id, track_info, expanded_bbox):
    """Draw ArUco marker detection and tracking info on frame."""
    x, y, w, h = expanded_bbox
    color = track_info["color"]

    # Draw bounding box
    cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)

    # Draw marker corners
    corners = track_info["corners"]
    corners_int = corners.astype(int)
    cv2.polylines(frame, [corners_int], True, color, 3)

    # Draw corner points
    for corner in corners_int:
        cv2.circle(frame, tuple(corner), 5, color, -1)

    # Draw center point
    center = track_info["center"]
    cv2.circle(frame, center, 8, color, -1)
    cv2.circle(frame, center, 10, (255, 255, 255), 2)

    # Draw marker ID
    data = str(marker_id)
    label = f"Bee ID: {data}"

    # Add detection count
    count = track_info["detection_count"]
    label += f" (n={count})"

    # Background for text
    (text_w, text_h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
    cv2.rectangle(frame, (x, y - text_h - 10), (x + text_w, y), color, -1)

    # Draw text
    cv2.putText(
        frame, label, (x, y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2
    )


def process_video(video_path, show=True, save=True):
    """Main video processing function."""

    print("\n" + "=" * 70)
    print("ArUco Marker-Based Bee Tracking (5x5)")
    print("=" * 70)
    print(f"\nVideo: {video_path}")
    print(f"ArUco Dictionary: {ARUCO_DICT}")
    print(f"Multi-scale detection: {'Enabled' if USE_MULTISCALE else 'Disabled'}")
    if USE_MULTISCALE:
        print(f"Scales to try: {SCALES}")

    # Open video
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"Error: Could not open video {video_path}")
        return

    # Get video properties
    fps = int(cap.get(cv2.CAP_PROP_FPS))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    print(f"Resolution: {width}x{height}")
    print(f"FPS: {fps}")
    print(f"Total frames: {total_frames}")

    # Initialize ArUco detector
    aruco_dict = cv2.aruco.getPredefinedDictionary(ARUCO_DICT)
    parameters = cv2.aruco.DetectorParameters()

    # Adjust detection parameters for small marker detection
    parameters.minMarkerPerimeterRate = MIN_MARKER_PERIMETER / max(width, height)
    parameters.maxMarkerPerimeterRate = MAX_MARKER_PERIMETER / max(width, height)
    parameters.adaptiveThreshWinSizeMin = 3  # Smaller window for small markers
    parameters.adaptiveThreshWinSizeMax = 23
    parameters.adaptiveThreshWinSizeStep = 4
    parameters.minDistanceToBorder = 0  # Allow markers at edges

    # Initialize tracker
    tracker = BarcodeTracker(max_frames_missing=MAX_FRAMES_MISSING)

    # Setup video writer
    out = None
    if save:
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        out = cv2.VideoWriter(OUTPUT_PATH, fourcc, fps, (width, height))
        print(f"Output: {OUTPUT_PATH}")

    # Statistics
    stats = {"total_detections": 0, "unique_bees": set(), "detections_per_frame": []}

    print("\nProcessing video... (Press 'q' to quit)\n")

    frame_number = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame_number += 1

        # Detect ArUco markers
        detections = detect_aruco_markers(frame, aruco_dict, parameters)

        # Update tracker
        active_tracks = tracker.update(detections, frame_number)

        # Update statistics
        stats["total_detections"] += len(detections)
        stats["unique_bees"].update([mid for mid, _ in active_tracks])
        stats["detections_per_frame"].append(len(detections))

        # Draw detections
        for marker_id, track_info in active_tracks:
            bbox = track_info["bbox"]
            expanded_bbox = expand_bbox(bbox, EXPAND_BOX, frame.shape)
            draw_barcode_info(frame, marker_id, track_info, expanded_bbox)

        # Draw frame info
        info_text = f"Frame: {frame_number}/{total_frames} | Active Bees: {len(active_tracks)} | Total Unique: {len(stats['unique_bees'])}"
        cv2.putText(
            frame, info_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2
        )

        # Save frame
        if out:
            out.write(frame)

        # Display
        if show:
            cv2.imshow("ArUco Tracking", frame)
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                print("\nProcessing stopped by user")
                break

        # Progress update
        if frame_number % 100 == 0:
            avg_detections = np.mean(stats["detections_per_frame"][-100:])
            print(
                f"  Frame {frame_number}/{total_frames} | "
                f"Active: {len(active_tracks)} | "
                f"Avg detections/frame: {avg_detections:.1f}"
            )

    # Cleanup
    cap.release()
    if out:
        out.release()
    cv2.destroyAllWindows()

    # Print summary
    print("\n" + "=" * 70)
    print("Processing Complete!")
    print("=" * 70)
    print("\nStatistics:")
    print(f"  Total frames processed: {frame_number}")
    print(f"  Total marker detections: {stats['total_detections']}")
    print(f"  Unique bees identified: {len(stats['unique_bees'])}")

    if stats["detections_per_frame"]:
        print(
            f"  Average detections per frame: {np.mean(stats['detections_per_frame']):.2f}"
        )
        print(f"  Max detections in single frame: {max(stats['detections_per_frame'])}")

    print("\nUnique Bee IDs (ArUco Markers):")
    for marker_id in sorted(stats["unique_bees"]):
        print(f"  - Marker ID: {marker_id}")

    if save:
        print(f"\nOutput saved to: {OUTPUT_PATH}")


def _test_barcode_detection(video_path):
    """Test ArUco marker detection on first frame only."""
    print("\n" + "=" * 70)
    print("Testing ArUco Marker Detection (5x5)")
    print("=" * 70)

    cap = cv2.VideoCapture(video_path)
    ret, frame = cap.read()
    cap.release()

    if not ret:
        print("Error: Could not read first frame")
        return

    # Initialize ArUco detector
    aruco_dict = cv2.aruco.getPredefinedDictionary(ARUCO_DICT)
    parameters = cv2.aruco.DetectorParameters()

    # Configure for small markers
    parameters.minMarkerPerimeterRate = MIN_MARKER_PERIMETER / max(frame.shape)
    parameters.maxMarkerPerimeterRate = MAX_MARKER_PERIMETER / max(frame.shape)
    parameters.adaptiveThreshWinSizeMin = 3
    parameters.adaptiveThreshWinSizeMax = 23
    parameters.minDistanceToBorder = 0

    print("\nDetecting ArUco markers in first frame...")
    print(
        f"Multi-scale: {USE_MULTISCALE}, Scales: {SCALES if USE_MULTISCALE else [1.0]}"
    )

    detections = detect_aruco_markers(frame, aruco_dict, parameters)

    print(f"\nFound {len(detections)} ArUco markers:")
    for i, (marker_id, corners, center, bbox) in enumerate(detections, 1):
        size = int(np.linalg.norm(corners[0] - corners[2]))
        print(f"  {i}. Marker ID: {marker_id}")
        print(f"     Center: {center}")
        print(f"     Size: {size} pixels")
        print(f"     Bbox: {bbox}")

    # Draw detections
    for marker_id, corners, center, bbox in detections:
        color = COLORS[0]
        # Draw expanded bbox
        expanded_bbox = expand_bbox(bbox, EXPAND_BOX, frame.shape)
        x, y, w, h = expanded_bbox
        cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)

        # Draw marker corners
        corners_int = corners.astype(int)
        cv2.polylines(frame, [corners_int], True, color, 3)

        # Draw center
        cv2.circle(frame, center, 8, color, -1)

        # Draw ID
        label = f"Bee ID: {marker_id}"
        cv2.putText(
            frame,
            label,
            (center[0] - 40, center[1] - 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            color,
            2,
        )

    # Show result
    cv2.imshow("ArUco Detection Test", frame)

    # Also show 2x zoomed version
    zoomed = cv2.resize(frame, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
    cv2.imshow("ArUco Detection Test - 2x Zoom", zoomed)

    # Save for inspection
    cv2.imwrite("aruco_test_result.jpg", frame)
    cv2.imwrite("aruco_test_result_2x.jpg", zoomed)

    print("\nResults saved to:")
    print("  - aruco_test_result.jpg (original)")
    print("  - aruco_test_result_2x.jpg (2x zoom)")
    print("\nPress any key to close...")
    cv2.waitKey(0)
    cv2.destroyAllWindows()


if __name__ == "__main__":
    import sys
    from pathlib import Path

    # Check if video exists
    if not Path(VIDEO_PATH).exists():
        print(f"\n❌ Error: Video not found: {VIDEO_PATH}")
        print("Please update VIDEO_PATH in the script.")
        sys.exit(1)

    print("\n" + "=" * 70)
    print("ArUco Marker-Based Bee Tracking (5x5)")
    print("=" * 70)
    print("\nSelect mode:")
    print("1. Test ArUco detection (first frame only)")
    print("2. Full video tracking")

    choice = input("\nEnter choice (1-2) or press Enter for default (2): ").strip()

    if choice == "1":
        _test_barcode_detection(VIDEO_PATH)
    else:
        process_video(VIDEO_PATH, show=SHOW_LIVE, save=SAVE_VIDEO)
