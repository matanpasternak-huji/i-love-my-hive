from ultralytics import YOLO

# Load YOLOv8 model (or use yolo11n.pt for latest)
model = YOLO("yolov8n.pt")  # n=nano (fast), s=small, m=medium, l=large, x=xlarge

# Run tracking on video
results = model.track(
    source="checks_white_light.mp4",
    show=True,  # Display results
    save=True,  # Save output video
    tracker="bytetrack.yaml",  # Tracking algorithm
    conf=0.3,  # Confidence threshold
    iou=0.5,  # IoU threshold for NMS
    classes=None,  # Track all classes (or specify [0] for person, etc.)
)

print("\nDone! Check runs/detect/track/ for output video")
