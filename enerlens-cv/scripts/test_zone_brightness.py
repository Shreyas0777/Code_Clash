import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import cv2
import yaml

from src.baseline_brightness import measure_brightness
from src.zones import ZoneMapper


def main():
    with open(
        PROJECT_ROOT / "config/settings.yaml",
        encoding="utf-8-sig",
    ) as file:
        settings = yaml.safe_load(file)

    with open(
        PROJECT_ROOT / "config/zones_webcam_test.json",
        encoding="utf-8-sig",
    ) as file:
        import json
        zone_config = json.load(file)

    mapper = ZoneMapper(PROJECT_ROOT / "config/zones_webcam_test.json")
    off_threshold = settings["brightness"]["off_threshold"]
    on_threshold = settings["brightness"]["on_threshold"]

    camera = cv2.VideoCapture(0)
    if not camera.isOpened():
        raise RuntimeError("Could not open webcam.")

    print("Zone brightness monitor running. Press Q to quit.")
    print("These zones are placeholders; calibrate them for the real camera.")

    reference_width, reference_height = zone_config["reference_resolution"]

    try:
        while True:
            success, frame = camera.read()
            if not success:
                break

            height, width = frame.shape[:2]
            scale_x = width / reference_width
            scale_y = height / reference_height

            for zone in mapper.zones:
                x1, y1, x2, y2 = zone["box"]

                x1 = round(x1 * scale_x)
                x2 = round(x2 * scale_x)
                y1 = round(y1 * scale_y)
                y2 = round(y2 * scale_y)

                # Skip zones that do not fit the current frame.
                x1 = max(0, min(width, x1))
                x2 = max(0, min(width, x2))
                y1 = max(0, min(height, y1))
                y2 = max(0, min(height, y2))

                if x2 <= x1 or y2 <= y1:
                    continue

                brightness = measure_brightness(
                    frame, (x1, y1, x2, y2)
                )

                if zone["type"] != "light":
                    state = "NOT_CALIBRATED"
                elif brightness <= off_threshold:
                    state = "OFF?"
                elif brightness >= on_threshold:
                    state = "ON?"
                else:
                    state = "UNKNOWN"

                cv2.rectangle(
                    frame, (x1, y1), (x2, y2), (0, 255, 0), 2
                )

                label = f"{zone['id']}: {brightness:.1f} {state}"
                text_y = max(20, y1 - 8)

                cv2.putText(
                    frame,
                    label,
                    (x1, text_y),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.45,
                    (0, 255, 0),
                    1,
                )

            cv2.imshow("EnerLens - Zone Brightness Monitor", frame)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    finally:
        camera.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
