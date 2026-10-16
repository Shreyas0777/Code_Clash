import json
from pathlib import Path


class ZoneMapper:
    """Map detection centers to configured equipment zones."""

    def __init__(self, config_path="config/zones_lab1.json"):
        path = Path(config_path)

        with path.open("r", encoding="utf-8-sig") as file:
            config = json.load(file)

        self.reference_width, self.reference_height = (
            config["reference_resolution"]
        )
        self.zones = config["zones"]

    def map_point(self, x, y, frame_width, frame_height):
        """Return the equipment ID containing a point, or None."""
        if frame_width <= 0 or frame_height <= 0:
            raise ValueError("Frame dimensions must be positive")

        scaled_x = x * self.reference_width / frame_width
        scaled_y = y * self.reference_height / frame_height

        for zone in self.zones:
            x1, y1, x2, y2 = zone["box"]

            if x1 <= scaled_x <= x2 and y1 <= scaled_y <= y2:
                return {
                    "id": zone["id"],
                    "type": zone["type"],
                }

        return None
