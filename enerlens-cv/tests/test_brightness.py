import numpy as np
import pytest

from src.baseline_brightness import (
    classify_brightness,
    measure_brightness,
)


def test_dark_region_is_off():
    assert classify_brightness(20, 50, 150) == "OFF"


def test_bright_region_is_on():
    assert classify_brightness(220, 50, 150) == "ON"


def test_middle_region_is_unknown():
    assert classify_brightness(100, 50, 150) == "UNKNOWN"


def test_measure_brightness():
    frame = np.full((100, 100, 3), 200, dtype=np.uint8)

    brightness = measure_brightness(frame, (10, 10, 50, 50))

    assert brightness == pytest.approx(200.0)


def test_invalid_box_is_rejected():
    frame = np.zeros((100, 100, 3), dtype=np.uint8)

    with pytest.raises(ValueError):
        measure_brightness(frame, (10, 10, 120, 50))
