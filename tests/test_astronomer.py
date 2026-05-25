from datetime import date

from src.services.astronomer import compute_sunset_azimuth, get_season


def test_sunset_azimuth_summer():
    azimuth, sunset_time = compute_sunset_azimuth(22.27, 113.58, date(2026, 6, 21))
    # Summer solstice: azimuth should be around 300-310 degrees (WNW)
    assert 295 < azimuth < 315


def test_sunset_azimuth_winter():
    azimuth, sunset_time = compute_sunset_azimuth(22.27, 113.58, date(2026, 12, 21))
    # Winter solstice: azimuth should be around 235-245 degrees (WSW)
    assert 230 < azimuth < 250


def test_sunset_azimuth_equinox():
    azimuth, sunset_time = compute_sunset_azimuth(22.27, 113.58, date(2026, 3, 20))
    # Equinox: azimuth should be around 265-275 degrees (W)
    assert 260 < azimuth < 280


def test_get_season():
    assert get_season(date(2026, 3, 21)) == "spring"
    assert get_season(date(2026, 6, 21)) == "summer"
    assert get_season(date(2026, 9, 23)) == "autumn"
    assert get_season(date(2026, 12, 21)) == "winter"
