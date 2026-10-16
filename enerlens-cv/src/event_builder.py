from datetime import datetime, timezone


VALID_STATES = {"ON", "OFF", "UNKNOWN"}
VALID_TYPES = {"light", "fan", "monitor"}


def build_event(
    room,
    source,
    model_version,
    people_count,
    room_empty_seconds,
    equipment,
    timestamp=None,
    energy_waste=None,
):
    """Build and validate a JSON-serializable EnerLens event."""

    if not room or not source or not model_version:
        raise ValueError("room, source, and model_version are required")

    if people_count < 0 or room_empty_seconds < 0:
        raise ValueError("People count and empty duration cannot be negative")

    if timestamp is None:
        timestamp = datetime.now(timezone.utc).astimezone().isoformat()

    validated_equipment = []
    seen_ids = set()

    for item in equipment:
        equipment_id = item.get("id")
        equipment_type = item.get("type")
        state = item.get("state")
        confidence = item.get("confidence")

        if not equipment_id or equipment_id in seen_ids:
            raise ValueError("Equipment IDs must be non-empty and unique")
        seen_ids.add(equipment_id)

        if equipment_type not in VALID_TYPES:
            raise ValueError(f"Invalid equipment type: {equipment_type}")

        if state not in VALID_STATES:
            raise ValueError(f"Invalid equipment state: {state}")

        if (
            not isinstance(confidence, (int, float))
            or isinstance(confidence, bool)
            or not 0 <= confidence <= 1
        ):
            raise ValueError("Confidence must be a number between 0 and 1")

        validated_equipment.append(
            {
                "id": equipment_id,
                "type": equipment_type,
                "state": state,
                "confidence": float(confidence),
            }
        )

    event = {
        "room": room,
        "timestamp": timestamp,
        "source": source,
        "model_version": model_version,
        "people_count": people_count,
        "room_empty_seconds": room_empty_seconds,
        "equipment": validated_equipment,
    }

    if energy_waste is not None:
        event["energy_waste"] = energy_waste

    return event
