from src.zones import ZoneMapper


def test_point_inside_light_zone():
    mapper = ZoneMapper()

    result = mapper.map_point(
        x=200,
        y=80,
        frame_width=1280,
        frame_height=720,
    )

    assert result == {"id": "light_1", "type": "light"}


def test_point_outside_all_zones():
    mapper = ZoneMapper()

    result = mapper.map_point(
        x=1250,
        y=700,
        frame_width=1280,
        frame_height=720,
    )

    assert result is None


def test_coordinates_scale_to_reference_resolution():
    mapper = ZoneMapper()

    result = mapper.map_point(
        x=100,
        y=40,
        frame_width=640,
        frame_height=360,
    )

    assert result == {"id": "light_1", "type": "light"}
def test_coordinates_scale_for_640x480_webcam():
    mapper = ZoneMapper()

    result = mapper.map_point(
        x=100,
        y=40,
        frame_width=640,
        frame_height=480,
    )

    assert result == {"id": "light_1", "type": "light"}
