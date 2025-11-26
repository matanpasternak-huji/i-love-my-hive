import os

import cv2

# Configuration
VIDEO_PATH = "checks_white_light.mp4"
OUTPUT_FOLDER = "frames"
INTERVAL_SECONDS = 10

# Create output folder
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Open video
cap = cv2.VideoCapture(VIDEO_PATH)

if not cap.isOpened():
    print(f"Error: Could not open video {VIDEO_PATH}")
    exit(1)

# Get video properties
fps = cap.get(cv2.CAP_PROP_FPS)
total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
duration_seconds = total_frames / fps

print(f"Video: {VIDEO_PATH}")
print(f"FPS: {fps:.2f}")
print(f"Total frames: {total_frames}")
print(f"Duration: {duration_seconds:.2f} seconds")
print(f"Extracting 1 frame every {INTERVAL_SECONDS} seconds")
print(f"Output folder: {OUTPUT_FOLDER}\n")

# Calculate frame interval
frame_interval = int(fps * INTERVAL_SECONDS)

frame_count = 0
saved_count = 0

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break

    # Save frame at intervals
    if frame_count % frame_interval == 0:
        timestamp = frame_count / fps
        filename = f"frame_{saved_count:04d}_t{timestamp:.1f}s.jpg"
        filepath = os.path.join(OUTPUT_FOLDER, filename)
        cv2.imwrite(filepath, frame)
        saved_count += 1
        print(f"Saved: {filename}")

    frame_count += 1

cap.release()

print(f"\nDone! Extracted {saved_count} frames to '{OUTPUT_FOLDER}/' folder")
