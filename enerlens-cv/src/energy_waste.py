VALID_STATES = {"ON", "OFF", "UNKNOWN"}


def assess_energy_waste(
    people_count,
    room_empty_seconds,
    equipment,
    empty_threshold_seconds=20,
):
    """Assess potential light waste using occupancy and light state."""

    if people_count < 0:
        raise ValueError("people_count cannot be negative")

    if room_empty_seconds < 0:
        raise ValueError("room_empty_seconds cannot be negative")

    if empty_threshold_seconds < 0:
        raise ValueError("empty_threshold_seconds cannot be negative")

    results = []

    for item in equipment:
        if item.get("type") != "light":
            continue

        state = item.get("state", "UNKNOWN")

        if state not in VALID_STATES:
            raise ValueError(f"Invalid equipment state: {state}")

        if state == "UNKNOWN":
            status = "INSUFFICIENT_INFORMATION"
            reason = "Light state is unknown"
        elif state == "OFF":
            status = "NO_WASTE_DETECTED"
            reason = "Light is off"
        elif people_count > 0:
            status = "NORMAL"
            reason = "People are present and the light is on"
        elif room_empty_seconds >= empty_threshold_seconds:
            status = "POSSIBLE_ENERGY_WASTE"
            reason = (
                "Light is on and the room has been empty for "
                f"at least {empty_threshold_seconds} seconds"
            )
        else:
            status = "WAITING"
            reason = "Room has not yet reached the empty-time threshold"

        results.append({
            "equipment_id": item.get("id", "unknown"),
            "status": status,
            "reason": reason,
        })

    return results
