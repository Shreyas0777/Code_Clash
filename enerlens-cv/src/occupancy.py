import time


class OccupancyTracker:
    """Track people count and continuous room-empty duration."""

    def __init__(self):
        self.empty_since = None

    def update(self, people_count, now=None):
        """
        Update occupancy state.

        Args:
            people_count: Number of people detected in the frame.
            now: Optional timestamp in seconds, useful for testing.
        """
        if people_count < 0:
            raise ValueError("people_count cannot be negative")

        if now is None:
            now = time.monotonic()

        if people_count > 0:
            self.empty_since = None
            empty_seconds = 0
        else:
            if self.empty_since is None:
                self.empty_since = now

            empty_seconds = int(now - self.empty_since)

        return {
            "people_count": people_count,
            "room_empty_seconds": empty_seconds,
            "room_is_empty": people_count == 0,
        }
