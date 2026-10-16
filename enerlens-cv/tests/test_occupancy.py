from src.occupancy import OccupancyTracker


def test_room_empty_timer():
    tracker = OccupancyTracker()

    first = tracker.update(0, now=100)
    assert first["room_empty_seconds"] == 0

    second = tracker.update(0, now=105)
    assert second["room_empty_seconds"] == 5

    occupied = tracker.update(1, now=106)
    assert occupied["room_empty_seconds"] == 0

    empty_again = tracker.update(0, now=110)
    assert empty_again["room_empty_seconds"] == 0

    later = tracker.update(0, now=114)
    assert later["room_empty_seconds"] == 4


def test_negative_people_count_is_rejected():
    tracker = OccupancyTracker()

    try:
        tracker.update(-1, now=100)
    except ValueError:
        return

    raise AssertionError("Negative people count should be rejected")
