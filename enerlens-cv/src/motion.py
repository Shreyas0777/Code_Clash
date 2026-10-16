import cv2
import numpy as np


class MotionDetector:
    """Estimate motion in a configured region using frame differencing."""

    def __init__(self, pixel_threshold=12, moving_pixel_ratio=0.02):
        if not 0 <= pixel_threshold <= 255:
            raise ValueError("pixel_threshold must be between 0 and 255")

        if not 0 <= moving_pixel_ratio <= 1:
            raise ValueError("moving_pixel_ratio must be between 0 and 1")

        self.pixel_threshold = pixel_threshold
        self.moving_pixel_ratio = moving_pixel_ratio
        self.previous_gray = None

    def update(self, frame, box=None):
        """
        Compare consecutive frames.

        Args:
            frame: Current BGR image.
            box: Optional (x1, y1, x2, y2) region.

        Returns:
            Dictionary containing motion ratio and status.
        """
        if frame is None or frame.size == 0:
            raise ValueError("Frame must be a non-empty image")

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        if box is not None:
            x1, y1, x2, y2 = map(int, box)
            height, width = gray.shape

            if not (0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height):
                raise ValueError("Box must be inside the frame")

            gray = gray[y1:y2, x1:x2]

        if self.previous_gray is None:
            self.previous_gray = gray.copy()
            return {
                "motion_ratio": 0.0,
                "motion_detected": False,
                "state": "UNKNOWN",
            }

        if gray.shape != self.previous_gray.shape:
            self.previous_gray = gray.copy()
            return {
                "motion_ratio": 0.0,
                "motion_detected": False,
                "state": "UNKNOWN",
            }

        difference = cv2.absdiff(gray, self.previous_gray)
        changed_pixels = difference > self.pixel_threshold
        ratio = float(np.count_nonzero(changed_pixels) / changed_pixels.size)

        self.previous_gray = gray.copy()
        moving = ratio >= self.moving_pixel_ratio

        return {
            "motion_ratio": ratio,
            "motion_detected": moving,
            "state": "ON" if moving else "OFF",
        }
