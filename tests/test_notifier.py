from datetime import date, datetime

from src.services.notifier import build_card_message
from src.schemas.sunset import SunsetForecast, LocationRecommendation


def test_build_card_message():
    forecast = SunsetForecast(
        city="广东省-珠海",
        event_date=date(2026, 5, 24),
        event_name="日落",
        quality_raw="0.350（中烧）",
        quality_value=0.35,
        quality_label="中烧",
        aod_raw="0.280（还不错）",
        aod_value=0.28,
        aod_label="还不错",
        model="EC",
        image_url="https://sunsetbot.top/img/test.jpg",
        fetch_time=datetime(2026, 5, 24, 16, 0, 0),
    )

    recs = [
        LocationRecommendation(
            name="情侣路",
            lat=22.2475,
            lon=113.5720,
            facing_azimuth=250.0,
            description="海滨步道",
            tags=["海边", "长廊"],
            map_url=None,
            score=0.95,
            reason="完美对齐",
            suggested_arrival="18:42",
        )
    ]

    card = build_card_message(forecast, recs)

    assert card["msg_type"] == "interactive"
    assert "中烧" in card["card"]["header"]["title"]["content"]
    assert card["card"]["header"]["template"] == "orange"


def test_build_card_high_quality():
    forecast = SunsetForecast(
        city="广东省-珠海",
        event_date=date(2026, 5, 24),
        event_name="日落",
        quality_raw="0.600（大烧）",
        quality_value=0.6,
        quality_label="大烧",
        aod_raw="0.200（还不错）",
        aod_value=0.2,
        aod_label="还不错",
        model="EC",
        image_url="",
        fetch_time=datetime(2026, 5, 24, 16, 0, 0),
    )

    card = build_card_message(forecast, [])
    assert card["card"]["header"]["template"] == "red"
