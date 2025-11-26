#!/usr/bin/env python3
"""
YOLOv8 Training Script for Bee Detection

This script trains a YOLOv8 model on the preprocessed bee dataset.
The trained model will be able to detect and track bees in videos.
"""

import torch
from ultralytics import YOLO

# ==================== CONFIGURATION ====================

# Dataset configuration
DATA_YAML = "yolo_dataset/data.yaml"

# Model selection - choose one:
# - yolov8n.pt: Nano (fastest, least accurate) - good for testing
# - yolov8s.pt: Small (fast, decent accuracy)
# - yolov8m.pt: Medium (balanced speed/accuracy) - RECOMMENDED
# - yolov8l.pt: Large (slower, more accurate)
# - yolov8x.pt: Extra large (slowest, most accurate)
MODEL_SIZE = "yolov8m.pt"

# Training hyperparameters
EPOCHS = 150  # Number of training epochs (increase for better results)
IMG_SIZE = 640  # Image size for training (640 or 1280)
BATCH_SIZE = 16  # Batch size (reduce if you run out of memory)
PATIENCE = 50  # Early stopping patience (stops if no improvement)

# Advanced settings
LEARNING_RATE = 0.01  # Initial learning rate
OPTIMIZER = "auto"  # Optimizer: 'SGD', 'Adam', 'AdamW', or 'auto'
AUGMENT = True  # Use data augmentation

# Auto-detect best device (MPS for Apple Silicon, CUDA for NVIDIA, CPU otherwise)
if torch.backends.mps.is_available():
    DEVICE = "mps"  # Apple Silicon GPU
elif torch.cuda.is_available():
    DEVICE = 0  # NVIDIA GPU
else:
    DEVICE = "cpu"  # CPU fallback

# Project organization
PROJECT_NAME = "bee_detection"
RUN_NAME = "yolov8m_150epochs"

# =======================================================


def train_model():
    """Train YOLOv8 model on bee dataset."""

    print("\n" + "=" * 70)
    print("YOLOv8 Bee Detection Training")
    print("=" * 70)

    print("\nConfiguration:")
    print(f"  Model: {MODEL_SIZE}")
    print(f"  Dataset: {DATA_YAML}")
    print(f"  Epochs: {EPOCHS}")
    print(f"  Image size: {IMG_SIZE}")
    print(f"  Batch size: {BATCH_SIZE}")
    print(f"  Device: {DEVICE}")
    print(f"  Output: runs/{PROJECT_NAME}/{RUN_NAME}/")

    # Load pretrained model
    print(f"\nLoading pretrained {MODEL_SIZE} model...")
    model = YOLO(MODEL_SIZE)

    # Train the model
    print("\nStarting training...\n")
    results = model.train(
        data=DATA_YAML,
        epochs=EPOCHS,
        imgsz=IMG_SIZE,
        batch=BATCH_SIZE,
        patience=PATIENCE,
        lr0=LEARNING_RATE,
        optimizer=OPTIMIZER,
        augment=AUGMENT,
        device=DEVICE,
        project=PROJECT_NAME,
        name=RUN_NAME,
        exist_ok=True,
        pretrained=True,
        verbose=True,
        # Additional useful settings
        save=True,  # Save checkpoints
        save_period=10,  # Save checkpoint every N epochs
        plots=True,  # Generate training plots
        cache=False,  # Cache images (use True if enough RAM)
        rect=False,  # Rectangular training
        cos_lr=True,  # Use cosine learning rate scheduler
        close_mosaic=10,  # Disable mosaic augmentation for last N epochs
        val=True,  # Validate during training
    )

    print("\n" + "=" * 70)
    print("Training Complete!")
    print("=" * 70)

    # Print results summary
    print(f"\nBest model saved to: {PROJECT_NAME}/{RUN_NAME}/weights/best.pt")
    print(f"Last model saved to: {PROJECT_NAME}/{RUN_NAME}/weights/last.pt")
    print(f"Training plots saved to: {PROJECT_NAME}/{RUN_NAME}/")

    # Validate on test set
    print("\nValidating best model on validation set...")
    metrics = model.val()

    print("\nValidation Results:")
    print(f"  mAP50: {metrics.box.map50:.4f}")
    print(f"  mAP50-95: {metrics.box.map:.4f}")
    print(f"  Precision: {metrics.box.mp:.4f}")
    print(f"  Recall: {metrics.box.mr:.4f}")

    print("\n" + "=" * 70)
    print("Next Steps:")
    print("=" * 70)
    print("\n1. Check training plots in the output directory")
    print("2. Test the model:")
    print("   python test_model.py")
    print("\n3. Use the model for inference:")
    print("   from ultralytics import YOLO")
    print(f"   model = YOLO('{PROJECT_NAME}/{RUN_NAME}/weights/best.pt')")
    print("   results = model.track(source='video.mp4', save=True)")
    print()


def resume_training(checkpoint_path):
    """Resume training from a checkpoint."""
    print(f"\nResuming training from: {checkpoint_path}")
    model = YOLO(checkpoint_path)
    results = model.train(resume=True)
    return results


if __name__ == "__main__":
    # Train from scratch
    train_model()

    # To resume training from a checkpoint, uncomment:
    # resume_training("bee_detection/yolov8m_150epochs/weights/last.pt")
