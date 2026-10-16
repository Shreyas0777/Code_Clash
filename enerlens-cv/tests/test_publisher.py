import json

from src.publisher import EventPublisher


def test_event_is_saved_as_jsonl(tmp_path):
    output = tmp_path / "events.jsonl"
    publisher = EventPublisher(output_path=output)

    event = {
        "room": "lab_1",
        "people_count": 1,
        "equipment": [],
    }

    result = publisher.publish(event)

    assert result["saved"] is True
    assert result["sent"] is False

    lines = output.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0]) == event


def test_multiple_events_are_appended(tmp_path):
    output = tmp_path / "events.jsonl"
    publisher = EventPublisher(output_path=output)

    publisher.publish({"people_count": 0})
    publisher.publish({"people_count": 2})

    lines = output.read_text(encoding="utf-8").splitlines()

    assert len(lines) == 2
    assert json.loads(lines[0])["people_count"] == 0
    assert json.loads(lines[1])["people_count"] == 2

def test_event_is_saved_when_backend_is_unavailable(tmp_path, monkeypatch):
    import requests

    output = tmp_path / "events.jsonl"
    publisher = EventPublisher(
        output_path=output,
        backend_url="http://localhost:8000/api/cv/events",
    )

    def fail_post(*args, **kwargs):
        raise requests.ConnectionError("Backend unavailable")

    monkeypatch.setattr(requests, "post", fail_post)

    event = {"room": "lab_1", "people_count": 0}
    result = publisher.publish(event)

    assert result["saved"] is True
    assert result["sent"] is False
    assert "error" in result
    assert json.loads(output.read_text(encoding="utf-8")) == event
