import pytest

from src.smoothing import StateSmoother


def test_majority_vote_stabilizes_state():
    smoother = StateSmoother(window_size=3)

    assert smoother.update("ON") == "ON"
    assert smoother.update("OFF") == "OFF"
    assert smoother.update("ON") == "ON"
    assert smoother.update("ON") == "ON"


def test_unknown_does_not_overwrite_valid_history():
    smoother = StateSmoother(window_size=3)

    smoother.update("ON")
    assert smoother.update("UNKNOWN") == "ON"


def test_invalid_state_is_rejected():
    smoother = StateSmoother()

    with pytest.raises(ValueError):
        smoother.update("MAYBE")


def test_window_size_must_be_positive():
    with pytest.raises(ValueError):
        StateSmoother(window_size=0)
