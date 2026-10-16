import cv2


def measure_brightness(frame, box):
    """
    Measure average grayscale brightness inside a region.

    Args:
        frame: OpenCV BGR image.
        box: (x1, y1, x2, y2) pixel coordinates.

    Returns:
        Average grayscale brightness from 0 to 255.
    """
    if frame is None or frame.size == 0:
        raise ValueError("Frame must be a non-empty image")

    x1, y1, x2, y2 = map(int, box)
    height, width = frame.shape[:2]

    if not (0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height):
        raise ValueError("Box must be inside the frame and have positive area")

    region = frame[y1:y2, x1:x2]
    grayscale = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)

    return float(grayscale.mean())


def classify_brightness(brightness, off_threshold, on_threshold):
    """
    Classify brightness using a calibrated threshold band.

    Returns UNKNOWN between the thresholds.
    """
    if not (0 <= off_threshold < on_threshold <= 255):
        raise ValueError("Thresholds must satisfy 0 <= off < on <= 255")

    if brightness <= off_threshold:
        return "OFF"
    if brightness >= on_threshold:
        return "ON"
    return "UNKNOWN"
