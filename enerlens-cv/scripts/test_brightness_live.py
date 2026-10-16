import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import cv2

from src.baseline_brightness import measure_brightness


def main():
    camera = cv2.VideoCapture(0)

    if not camera.isOpened():
        raise RuntimeError("Could not open webcam.")

    print("Move between bright and dark conditions.")
    print("Press Q to quit.")

    try:
        while True:
            success, frame = camera.read()
            if not success:
                print("Could not read webcam frame.")
                break

            height, width = frame.shape[:2]

            # Central region of the webcam frame.
            x1, y1 = width // 4, height // 4
            x2, y2 = 3 * width // 4, 3 * height // 4

            brightness = measure_brightness(
                frame, (x1, y1, x2, y2)
            )

            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(
                frame,
                f"Average brightness: {brightness:.1f}/255",
                (20, 35),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 0),
                2,
            )

            cv2.imshow("EnerLens - Brightness Calibration", frame)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    finally:
        camera.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
