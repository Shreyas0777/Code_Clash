import json
from pathlib import Path

import requests


class EventPublisher:
    """Save EnerLens events locally and optionally POST them to a backend."""

    def __init__(
        self,
        output_path="outputs/events.jsonl",
        backend_url=None,
        timeout_seconds=2,
    ):
        self.output_path = Path(output_path)
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self.backend_url = backend_url
        self.timeout_seconds = timeout_seconds

    def publish(self, event):
        """Append an event locally, then attempt backend delivery if configured."""
        with self.output_path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(event, ensure_ascii=False) + "\n")

        if not self.backend_url:
            return {"saved": True, "sent": False, "status_code": None}

        try:
            response = requests.post(
                self.backend_url,
                json=event,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()

            return {
                "saved": True,
                "sent": True,
                "status_code": response.status_code,
            }
        except requests.RequestException as exc:
            # The local event remains saved even if backend delivery fails.
            return {
                "saved": True,
                "sent": False,
                "status_code": None,
                "error": str(exc),
            }
