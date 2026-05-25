from datetime import date, datetime

from pydantic import BaseModel


class SunsetForecast(BaseModel):
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
    sunset_azimuth: float | None = None
    sunset_time: datetime | None = None
    fetch_time: datetime


class SunsetRecordResponse(BaseModel):
    id: int
    city: str
    event_date: date
    event_time: datetime | None
    event_type: str
    model: str
    quality_value: float | None
    quality_label: str | None
    aod_value: float | None
    aod_label: str | None
    image_url: str | None
    sunset_azimuth: float | None
    fetch_time: datetime
    notified: bool

    model_config = {"from_attributes": True}


class LocationRecommendation(BaseModel):
    name: str
    lat: float
    lon: float
    facing_azimuth: float
    description: str
    tags: list[str]
    map_url: str | None
    score: float
    reason: str
    suggested_arrival: str  # "18:40"
