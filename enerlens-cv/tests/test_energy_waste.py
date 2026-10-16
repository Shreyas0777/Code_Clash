from src.energy_waste import assess_energy_waste


def test_empty_room_light_on_flags_possible_waste():
    equipment = [{"id": "light_1", "type": "light", "state": "ON"}]
    result = assess_energy_waste(0, 25, equipment)
    assert result[0]["status"] == "POSSIBLE_ENERGY_WASTE"


def test_people_present_is_normal():
    equipment = [{"id": "light_1", "type": "light", "state": "ON"}]
    result = assess_energy_waste(2, 0, equipment)
    assert result[0]["status"] == "NORMAL"


def test_short_empty_period_waits():
    equipment = [{"id": "light_1", "type": "light", "state": "ON"}]
    result = assess_energy_waste(0, 10, equipment)
    assert result[0]["status"] == "WAITING"


def test_light_off_has_no_waste_detected():
    equipment = [{"id": "light_1", "type": "light", "state": "OFF"}]
    result = assess_energy_waste(0, 30, equipment)
    assert result[0]["status"] == "NO_WASTE_DETECTED"


def test_unknown_light_state_is_insufficient_information():
    equipment = [{"id": "light_1", "type": "light", "state": "UNKNOWN"}]
    result = assess_energy_waste(0, 30, equipment)
    assert result[0]["status"] == "INSUFFICIENT_INFORMATION"


def test_non_light_equipment_is_ignored():
    equipment = [{"id": "fan_1", "type": "fan", "state": "ON"}]
    result = assess_energy_waste(0, 30, equipment)
    assert result == []


def test_negative_people_count_is_rejected():
    try:
        assess_energy_waste(-1, 30, [])
    except ValueError:
        return
    assert False, "Expected ValueError for negative people count"


def test_negative_empty_duration_is_rejected():
    try:
        assess_energy_waste(0, -1, [])
    except ValueError:
        return
    assert False, "Expected ValueError for negative empty duration"
