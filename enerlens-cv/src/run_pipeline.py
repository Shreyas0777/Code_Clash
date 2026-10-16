import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import cv2
import yaml

from src.detector import PersonDetector
from src.occupancy import OccupancyTracker
from src.event_builder import build_event
from src.publisher import EventPublisher
from src.motion import MotionDetector
from src.energy_waste import assess_energy_waste


def main():
    with open(
        PROJECT_ROOT / "config/settings.yaml",
        encoding="utf-8-sig",
    ) as file:
        settings = yaml.safe_load(file)

    detector = PersonDetector(
        model_path="yolov8n.pt",
        confidence=settings["detection"]["person_confidence"],
    )
    occupancy = OccupancyTracker()

    motion_detector = MotionDetector(
        pixel_threshold=settings["fan_motion"]["pixel_difference_threshold"],
        moving_pixel_ratio=settings["fan_motion"]["moving_pixel_ratio"],
    )

    equipment = [
        {"id": "light_1", "type": "light", "state": "UNKNOWN", "confidence": 0.0},
        {"id": "light_2", "type": "light", "state": "UNKNOWN", "confidence": 0.0},
        {"id": "fan_1", "type": "fan", "state": "UNKNOWN", "confidence": 0.0},
        {"id": "monitor_1", "type": "monitor", "state": "UNKNOWN", "confidence": 0.0},
    ]

    publisher = EventPublisher(
        output_path=PROJECT_ROOT / "outputs/events.jsonl",
        backend_url=settings["publishing"].get("backend_url") or None,
    )

    camera = cv2.VideoCapture(0)
    if not camera.isOpened():
        raise RuntimeError("Could not open webcam.")

    frame_number = 0
    last_publish = 0.0
    latest_count = 0
    latest_frame = None
    occupancy_result = occupancy.update(0)

    empty_threshold = settings["occupancy"]["empty_threshold_seconds"]

    print("EnerLens pipeline running. Press Q to quit.")
    print("Events are saved locally; backend publishing is attempted if configured.")

    try:
        while True:
            success, frame = camera.read()
            if not success:
                print("Could not read webcam frame.")
                break

            frame_number += 1
            process_every = settings["camera"]["process_every_n_frames"]

            if frame_number % process_every == 0:
                motion_detector.update(frame)

                result = detector.detect(frame)
                latest_count = result["people_count"]
                latest_frame = result["frame"]
                occupancy_result = occupancy.update(latest_count)

            display_frame = (
                latest_frame.copy()
                if latest_frame is not None
                else frame.copy()
            )

            cv2.putText(
                display_frame,
                f"People: {latest_count}",
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (0, 255, 0),
                2,
            )

            cv2.imshow("EnerLens CV Pipeline", display_frame)

            now = time.monotonic()
            if now - last_publish >= settings["publishing"]["interval_seconds"]:
                empty_seconds = occupancy_result["room_empty_seconds"]

                waste_assessment = assess_energy_waste(
                    people_count=latest_count,
                    room_empty_seconds=empty_seconds,
                    equipment=equipment,
                    empty_threshold_seconds=empty_threshold,
                )

                event = build_event(
                    room=settings["room"],
                    source=settings["source"],
                    model_version=settings["model"]["version"],
                    people_count=latest_count,
                    room_empty_seconds=empty_seconds,
                    equipment=equipment,
                    energy_waste=waste_assessment,
                )
                publisher.publish(event)

                print(
                    f"Saved event | people={latest_count} | "
                    f"empty_seconds={empty_seconds} | "
                    f"energy_waste={waste_assessment}"
                )
                last_publish = now

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    finally:
        camera.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
