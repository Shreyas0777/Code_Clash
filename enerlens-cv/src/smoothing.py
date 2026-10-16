from collections import Counter, deque


class StateSmoother:
    """Stabilize equipment states using a rolling majority vote."""

    VALID_STATES = {"ON", "OFF", "UNKNOWN"}

    def __init__(self, window_size=15):
        if window_size < 1:
            raise ValueError("window_size must be at least 1")

        self.history = deque(maxlen=window_size)

    def update(self, state):
        if state not in self.VALID_STATES:
            raise ValueError(f"Invalid state: {state}")

        # UNKNOWN observations do not overwrite valid state history.
        if state != "UNKNOWN":
            self.history.append(state)

        if not self.history:
            return "UNKNOWN"

        counts = Counter(self.history)

        # In a tie, return the most recently observed state among
        # the tied states.
        highest_count = max(counts.values())
        tied_states = {
            candidate
            for candidate, count in counts.items()
            if count == highest_count
        }

        for candidate in reversed(self.history):
            if candidate in tied_states:
                return candidate

        return "UNKNOWN"
