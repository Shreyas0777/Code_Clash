import pytest

from src.event_builder import build_event


def test_build_valid_event():
    event = build_event(
        room="lab_1",
        source="camera_1",
        model_version="yolov8n-energy-v1",
        people_count=1,
        room_empty_seconds=0,
        equipment=[
            {
                "id": "light_1",
                "type": "light",
                "state": "ON",
                "confidence": 0.91,
            }
        ],
        timestamp="2026-10-15T15:02:10+05:30",
    )

    assert event["room"] == "lab_1"
    assert event["people_count"] == 1
    assert event["equipment"][0]["state"] == "ON"


def test_invalid_state_is_rejected():
    with pytest.raises(ValueError):
        build_event(
            room="lab_1",
            source="camera_1",
            model_version="test",
            people_count=0,
            room_empty_seconds=0,
            equipment=[
                {
                    "id": "light_1",
                    "type": "light",
                    "state": "MAYBE",
                    "confidence": 0.8,
                }
            ],
        )


def test_confidence_must_be_between_zero_and_one():
    with pytest.raises(ValueError):
        build_event(
            room="lab_1",
            source="camera_1",
            model_version="test",
            people_count=0,
            room_empty_seconds=0,
            equipment=[
                {
                    "id": "light_1",
                    "type": "light",
                    "state": "OFF",
                    "confidence": 1.5,
                }
            ],
        )


def test_duplicate_equipment_ids_are_rejected():
    item = {
        "id": "light_1",
        "type": "light",
        "state": "ON",
        "confidence": 0.9,
    }

    with pytest.raises(ValueError):
        build_event(
            room="lab_1",
            source="camera_1",
            model_version="test",
            people_count=0,
            room_empty_seconds=0,
            equipment=[item, item],
        )
