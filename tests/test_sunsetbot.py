from src.services.sunsetbot import _parse_rated_value, _parse_event_date


def test_parse_rated_value():
    value, label = _parse_rated_value("0.175（小烧）")
    assert value == 0.175
    assert label == "小烧"


def test_parse_rated_value_with_spaces():
    value, label = _parse_rated_value(" 0.305 （一般） ")
    assert value == 0.305
    assert label == "一般"


def test_parse_rated_value_no_label():
    value, label = _parse_rated_value("0.5")
    assert value == 0.5
    assert label == ""


def test_parse_event_date():
    dt = _parse_event_date("2026年05月24日 19:36:33")
    assert dt.year == 2026
    assert dt.month == 5
    assert dt.day == 24
    assert dt.hour == 19
    assert dt.minute == 36
    assert dt.second == 33
