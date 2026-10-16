import sys
import time
import json
from pathlib import Path

import cv2
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.baseline_brightness import measure_brightness


def main():
    with open(
        PROJECT_ROOT / "config/zones_webcam_test.json",
        encoding="utf-8-sig",
    ) as file:
        config = json.load(file)

    with open(
        PROJECT_ROOT / "config/settings.yaml",
        encoding="utf-8-sig",
    ) as file:
        settings = yaml.safe_load(file)

    zone = config["zones"][0]
    x1, y1, x2, y2 = zone["box"]

    camera = cv2.VideoCapture(0)
    if not camera.isOpened():
        raise RuntimeError("Could not open webcam.")

    values = []
    start = time.monotonic()

    print("Sampling brightness for 10 seconds. Keep the camera still.")
    print("Press Q to stop early.")

    try:
        while time.monotonic() - start < 10:
            success, frame = camera.read()
            if not success:
                break

            height, width = frame.shape[:2]
            scale_x = width / config["reference_resolution"][0]
            scale_y = height / config["reference_resolution"][1]

            box = (
                round(x1 * scale_x),
                round(y1 * scale_y),
                round(x2 * scale_x),
                round(y2 * scale_y),
            )

            brightness = measure_brightness(frame, box)
            values.append(brightness)

            cv2.rectangle(
                frame, (box[0], box[1]), (box[2], box[3]),
                (0, 255, 0), 2
            )
            cv2.putText(
                frame,
                f"Brightness: {brightness:.1f}",
                (box[0], max(20, box[1] - 8)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 255, 0),
                1,
            )
            cv2.imshow("Brightness Stability Test", frame)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    finally:
        camera.release()
        cv2.destroyAllWindows()

    if not values:
        print("No brightness readings were collected.")
        return

    off_threshold = settings["brightness"]["off_threshold"]
    on_threshold = settings["brightness"]["on_threshold"]

    print(f"Samples collected: {len(values)}")
    print(f"Minimum brightness: {min(values):.1f}")
    print(f"Maximum brightness: {max(values):.1f}")
    print(f"Average brightness: {sum(values) / len(values):.1f}")
    print(f"Brightness range: {max(values) - min(values):.1f}")
    print(f"Current thresholds: OFF <= {off_threshold}, ON >= {on_threshold}")


if __name__ == "__main__":
    main()