#!/usr/bin/env python3
"""
Preprocess CVAT annotations and video frames for YOLOv8 training.

This script:
1. Extracts the first 1200 frames from the video
2. Deletes annotation files for frames 1200+ (they're not properly annotated)
3. Reorganizes everything into YOLOv8-compatible structure
"""

import os
import shutil
from pathlib import Path

import cv2

# ==================== CONFIGURATION ====================
VIDEO_PATH = "checks_white_light.mp4"
ANNOTATION_DIR = "_1200_first_frames_"
OUTPUT_DIR = "yolo_dataset"
NUM_VALID_FRAMES = 1200  # Only first 1200 frames are properly annotated
# =======================================================


def extract_frames_from_video(video_path, output_dir, num_frames):
    """Extract the first N frames from video and save as images."""
    print(f"\n{'='*60}")
    print(f"STEP 1: Extracting first {num_frames} frames from video")
    print(f"{'='*60}")

    os.makedirs(output_dir, exist_ok=True)

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Cannot open video: {video_path}")

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    print(f"Video info: {total_frames} frames, {fps:.2f} FPS")
    print(f"Extracting frames 0-{num_frames-1}...\n")

    frame_count = 0
    saved_count = 0

    while frame_count < num_frames:
        ret, frame = cap.read()
        if not ret:
            print(
                f"Warning: Could only extract {frame_count} frames (expected {num_frames})"
            )
            break

        # Save frame with same naming convention as annotations
        filename = f"frame_{frame_count:06d}.jpg"
        filepath = os.path.join(output_dir, filename)
        cv2.imwrite(filepath, frame)
        saved_count += 1

        if saved_count % 100 == 0:
            print(f"  Extracted {saved_count}/{num_frames} frames...")

        frame_count += 1

    cap.release()
    print(f"\n✓ Extracted {saved_count} frames to {output_dir}/\n")
    return saved_count


def clean_annotation_files(annotation_dir, num_valid_frames):
    """Delete annotation files for frames beyond num_valid_frames."""
    print(f"\n{'='*60}")
    print("STEP 2: Cleaning annotation files")
    print(f"{'='*60}")

    obj_train_data = Path(annotation_dir) / "obj_train_data"

    # Find all .txt files
    all_txt_files = sorted(obj_train_data.glob("frame_*.txt"))
    print(f"Found {len(all_txt_files)} annotation files")

    deleted_count = 0
    kept_count = 0

    for txt_file in all_txt_files:
        # Extract frame number from filename (e.g., frame_001234.txt -> 1234)
        frame_num = int(txt_file.stem.split("_")[1])

        if frame_num >= num_valid_frames:
            txt_file.unlink()
            deleted_count += 1
        else:
            kept_count += 1

    print(f"\n✓ Kept {kept_count} annotation files (frames 0-{num_valid_frames-1})")
    print(f"✓ Deleted {deleted_count} annotation files (frames {num_valid_frames}+)\n")
    return kept_count


def create_yolo8_structure(annotation_dir, frames_dir, output_dir, num_frames):
    """Organize data into YOLOv8 training structure."""
    print(f"\n{'='*60}")
    print("STEP 3: Creating YOLOv8 dataset structure")
    print(f"{'='*60}")

    # YOLOv8 expects this structure:
    # dataset/
    #   ├── images/
    #   │   ├── train/
    #   │   └── val/
    #   ├── labels/
    #   │   ├── train/
    #   │   └── val/
    #   └── data.yaml

    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)

    # Create directory structure
    train_images_dir = output_path / "images" / "train"
    val_images_dir = output_path / "images" / "val"
    train_labels_dir = output_path / "labels" / "train"
    val_labels_dir = output_path / "labels" / "val"

    for dir_path in [
        train_images_dir,
        val_images_dir,
        train_labels_dir,
        val_labels_dir,
    ]:
        dir_path.mkdir(parents=True, exist_ok=True)

    # Split data: 80% train, 20% val
    split_idx = int(num_frames * 0.8)
    print(f"Splitting data: {split_idx} train, {num_frames - split_idx} val")

    annotation_src = Path(annotation_dir) / "obj_train_data"
    frames_src = Path(frames_dir)

    copied_train = 0
    copied_val = 0

    for i in range(num_frames):
        frame_name = f"frame_{i:06d}"

        # Determine if train or val
        if i < split_idx:
            img_dest = train_images_dir
            lbl_dest = train_labels_dir
            copied_train += 1
        else:
            img_dest = val_images_dir
            lbl_dest = val_labels_dir
            copied_val += 1

        # Copy image
        img_src = frames_src / f"{frame_name}.jpg"
        if img_src.exists():
            shutil.copy2(img_src, img_dest / f"{frame_name}.jpg")

        # Copy label
        lbl_src = annotation_src / f"{frame_name}.txt"
        if lbl_src.exists():
            shutil.copy2(lbl_src, lbl_dest / f"{frame_name}.txt")

        if (i + 1) % 200 == 0:
            print(f"  Copied {i + 1}/{num_frames} files...")

    print(f"\n✓ Copied {copied_train} training samples")
    print(f"✓ Copied {copied_val} validation samples")

    # Create data.yaml for YOLOv8
    data_yaml_content = f"""# YOLOv8 Dataset Configuration
# Generated from CVAT annotations

path: {output_path.absolute()}  # dataset root dir
train: images/train  # train images (relative to 'path')
val: images/val  # val images (relative to 'path')

# Classes
names:
  0: Bee

# Dataset info
nc: 1  # number of classes
"""

    yaml_path = output_path / "data.yaml"
    with open(yaml_path, "w") as f:
        f.write(data_yaml_content)

    print(f"✓ Created {yaml_path}\n")

    return output_path


def verify_dataset(dataset_dir):
    """Verify the created dataset."""
    print(f"\n{'='*60}")
    print("STEP 4: Verifying dataset")
    print(f"{'='*60}")

    dataset_path = Path(dataset_dir)

    # Count files
    train_images = list((dataset_path / "images" / "train").glob("*.jpg"))
    val_images = list((dataset_path / "images" / "val").glob("*.jpg"))
    train_labels = list((dataset_path / "labels" / "train").glob("*.txt"))
    val_labels = list((dataset_path / "labels" / "val").glob("*.txt"))

    print("\nDataset structure:")
    print(f"  Train images: {len(train_images)}")
    print(f"  Train labels: {len(train_labels)}")
    print(f"  Val images:   {len(val_images)}")
    print(f"  Val labels:   {len(val_labels)}")

    # Check for mismatches
    if len(train_images) != len(train_labels):
        print("  ⚠️  Warning: Train images/labels count mismatch!")
    if len(val_images) != len(val_labels):
        print("  ⚠️  Warning: Val images/labels count mismatch!")

    # Sample a few annotations to verify format
    if train_labels:
        sample_label = train_labels[0]
        print(f"\nSample annotation ({sample_label.name}):")
        with open(sample_label, "r") as f:
            lines = f.readlines()[:3]  # Show first 3 lines
            for line in lines:
                print(f"  {line.strip()}")
        print(f"  ... ({len(lines)} annotations in this file)")

    print("\n✓ Dataset ready for YOLOv8 training!")
    print("\nTo train YOLOv8, run:")
    print(
        f"  yolo train data={dataset_path.absolute()}/data.yaml model=yolov8n.pt epochs=100 imgsz=640"
    )


def main():
    """Main preprocessing pipeline."""
    print("\n" + "=" * 60)
    print("YOLOv8 Dataset Preparation Script")
    print("=" * 60)

    # Verify input files exist
    if not os.path.exists(VIDEO_PATH):
        raise FileNotFoundError(f"Video not found: {VIDEO_PATH}")
    if not os.path.exists(ANNOTATION_DIR):
        raise FileNotFoundError(f"Annotation directory not found: {ANNOTATION_DIR}")

    # Create temporary directory for extracted frames
    temp_frames_dir = "temp_extracted_frames"

    try:
        # Step 1: Extract frames from video
        num_extracted = extract_frames_from_video(
            VIDEO_PATH, temp_frames_dir, NUM_VALID_FRAMES
        )

        # Step 2: Clean annotation files
        num_annotations = clean_annotation_files(ANNOTATION_DIR, NUM_VALID_FRAMES)

        # Step 3: Create YOLOv8 structure
        dataset_path = create_yolo8_structure(
            ANNOTATION_DIR,
            temp_frames_dir,
            OUTPUT_DIR,
            min(num_extracted, num_annotations, NUM_VALID_FRAMES),
        )

        # Step 4: Verify
        verify_dataset(dataset_path)

        print("\n" + "=" * 60)
        print("✓ PREPROCESSING COMPLETE!")
        print("=" * 60)
        print(f"\nYour dataset is ready at: {dataset_path.absolute()}")
        print("You can now train YOLOv8 on your bee annotations.")

    finally:
        # Cleanup temporary frames directory
        if os.path.exists(temp_frames_dir):
            print(f"\nCleaning up temporary directory: {temp_frames_dir}")
            shutil.rmtree(temp_frames_dir)
            print("✓ Cleanup complete")


if __name__ == "__main__":
    main()
