import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import cv2
import yaml

from src.baseline_brightness import (
    classify_brightness,
    measure_brightness,
)


def main():
    with open(
        PROJECT_ROOT / "config/settings.yaml",
        encoding="utf-8-sig",
    ) as file:
        settings = yaml.safe_load(file)

    off_threshold = settings["brightness"]["off_threshold"]
    on_threshold = settings["brightness"]["on_threshold"]

    camera = cv2.VideoCapture(0)

    if not camera.isOpened():
        raise RuntimeError("Could not open webcam.")

    print("Press Q to quit.")

    try:
        while True:
            success, frame = camera.read()
            if not success:
                break

            height, width = frame.shape[:2]
            box = (
                width // 4,
                height // 4,
                3 * width // 4,
                3 * height // 4,
            )

            brightness = measure_brightness(frame, box)
            state = classify_brightness(
                brightness,
                off_threshold,
                on_threshold,
            )

            x1, y1, x2, y2 = box
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)

            label = f"Brightness: {brightness:.1f} | State: {state}"
            cv2.putText(
                frame,
                label,
                (15, 35),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                (0, 255, 0),
                2,
            )

            cv2.imshow("EnerLens - Provisional Brightness Classifier", frame)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    finally:
        camera.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
