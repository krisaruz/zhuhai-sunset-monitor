import random
from dataclasses import dataclass
from datetime import date, datetime

import httpx

from src.config import settings


@dataclass(frozen=True)
class SunsetForecast:
    city: str
    event_date: date
    event_name: str  # 日落 or 日出
    quality_raw: str
    quality_value: float
    quality_label: str
    aod_raw: str
    aod_value: float
    aod_label: str
    model: str
    image_url: str
    fetch_time: datetime


def _parse_rated_value(raw: str) -> tuple[float, str]:
    """Parse '0.175（小烧）' -> (0.175, '小烧')"""
    cleaned = raw.strip()
    parts = cleaned.split("（")
    value = float(parts[0].strip())
    label = parts[1].rstrip("）").strip() if len(parts) > 1 else ""
    return value, label


def _parse_event_date(s: str) -> datetime:
    """Parse '2026年05月24日 19:36:33' -> datetime"""
    return datetime.strptime(s.strip(), "%Y年%m月%d日 %H:%M:%S")


def _extract_event_date_as_date(dt: datetime) -> date:
    return dt.date()


async def fetch_forecast(
    city: str | None = None,
    event: str = "set_1",
    model: str | None = None,
) -> SunsetForecast | None:
    """
    Fetch sunset/sunrise forecast from sunsetbot.top.

    Args:
        city: City name (default: settings.default_city)
        event: 'set_1'(today sunset), 'set_2'(tomorrow sunset),
               'rise_1'(today sunrise), 'rise_2'(tomorrow sunrise)
        model: 'EC' or 'GFS' (default: settings.sunsetbot_model)

    Returns:
        SunsetForecast or None if data unavailable
    """
    city = city or settings.default_city
    model = model or settings.sunsetbot_model

    params = {
        "query_id": str(random.randint(1000000, 9999999)),
        "intend": "select_city",
        "query_city": city,
        "event": event,
        "event_date": "None",
        "times": "None",
        "model": model,
    }

    last_error: Exception | None = None
    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(settings.sunsetbot_base_url, params=params)
                resp.raise_for_status()
                data = resp.json()

            if data.get("status") != "ok":
                return None

            quality_value, quality_label = _parse_rated_value(data["tb_quality"])
            aod_value, aod_label = _parse_rated_value(data["tb_aod"])

            event_dt = _parse_event_date(data["display_event_date_str"])
            img_url = f"https://sunsetbot.top{data['img_href']}"

            return SunsetForecast(
                city=data["display_city_name"],
                event_date=_extract_event_date_as_date(event_dt),
                event_name=data["display_event_name_cn"],
                quality_raw=data["tb_quality"],
                quality_value=quality_value,
                quality_label=quality_label,
                aod_raw=data["tb_aod"],
                aod_value=aod_value,
                aod_label=aod_label,
                model=data["display_model"],
                image_url=img_url,
                fetch_time=datetime.now(),
            )
        except Exception as e:
            last_error = e
            import asyncio
            await asyncio.sleep(2 ** attempt)

    return None
