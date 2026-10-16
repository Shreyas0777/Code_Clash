import numpy as np
import pytest

from src.motion import MotionDetector


def test_first_frame_is_unknown():
    detector = MotionDetector()
    frame = np.zeros((100, 100, 3), dtype=np.uint8)

    result = detector.update(frame)

    assert result["state"] == "UNKNOWN"


def test_identical_frames_have_no_motion():
    detector = MotionDetector()
    frame = np.zeros((100, 100, 3), dtype=np.uint8)

    detector.update(frame)
    result = detector.update(frame.copy())

    assert result["motion_detected"] is False
    assert result["state"] == "OFF"
    assert result["motion_ratio"] == 0.0


def test_changed_frame_detects_motion():
    detector = MotionDetector(
        pixel_threshold=12,
        moving_pixel_ratio=0.02,
    )

    first = np.zeros((100, 100, 3), dtype=np.uint8)
    second = first.copy()
    second[20:80, 20:80] = 255

    detector.update(first)
    result = detector.update(second)

    assert result["motion_detected"] is True
    assert result["state"] == "ON"
    assert result["motion_ratio"] > 0.02


def test_invalid_threshold_is_rejected():
    with pytest.raises(ValueError):
        MotionDetector(pixel_threshold=300)


def test_invalid_box_is_rejected():
    detector = MotionDetector()
    frame = np.zeros((100, 100, 3), dtype=np.uint8)

    with pytest.raises(ValueError):
        detector.update(frame, box=(10, 10, 120, 50))
