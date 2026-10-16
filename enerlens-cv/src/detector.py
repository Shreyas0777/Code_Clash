from ultralytics import YOLO


class PersonDetector:
    """Detect people using the pretrained COCO YOLO model."""

    PERSON_CLASS_ID = 0

    def __init__(self, model_path="yolov8n.pt", confidence=0.40):
        self.model = YOLO(model_path)
        self.confidence = confidence

    def detect(self, frame):
        """Return person detections and the annotated frame."""
        results = self.model.predict(
            source=frame,
            classes=[self.PERSON_CLASS_ID],
            conf=self.confidence,
            verbose=False,
        )

        result = results[0]
        people = []

        if result.boxes is not None:
            for box in result.boxes:
                x1, y1, x2, y2 = box.xyxy[0].tolist()

                people.append(
                    {
                        "box": [
                            int(x1),
                            int(y1),
                            int(x2),
                            int(y2),
                        ],
                        "confidence": float(box.conf[0]),
                    }
                )

        annotated_frame = result.plot()

        return {
            "people_count": len(people),
            "people": people,
            "frame": annotated_frame,
        }
