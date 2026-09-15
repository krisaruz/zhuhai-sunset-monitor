"""Open-Meteo 数据源：三层云量 + 湿度 + AOD，自算晚霞鲜艳度评分。

替代已不可用的 sunsetbot.top。quality_value 由日落前后云层结构启发式计算，
AOD 直接采用 Open-Meteo CAMS 的 aerosol_optical_depth（与 sunsetbot 同一物理量）。
"""

import logging
from dataclasses import dataclass
from datetime import date, datetime, timezone, timedelta

import httpx

from src.config import settings

logger = logging.getLogger("open-meteo")

WEATHER_URL = "https://api.open-meteo.com/v1/forecast"
AIR_QUALITY_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"

HKT = timezone(timedelta(hours=8))

# 日落评分关注的时间窗：日落前后各 1 小时
WINDOW_BEFORE_H = 1
WINDOW_AFTER_H = 1


@dataclass(frozen=True)
class OMSunsetForecast:
    city: str
    event_date: date
    quality_value: float
    quality_label: str
    quality_raw: str
    aod_value: float
    aod_label: str
    aod_raw: str
    model: str
    image_url: str
    fetch_time: datetime
    event_name: str


def classify_quality(value: float) -> str:
    """按 analyzer._classify_burn 的同一口径生成烧级标签。"""
    if value >= 0.8:
        return "大烧"
    elif value >= 0.6:
        return "中烧到大烧"
    elif value >= 0.4:
        return "中等烧"
    elif value >= 0.2:
        return "小烧到中烧"
    elif value >= 0.05:
        return "小烧"
    elif value >= 0.01:
        return "微烧"
    return "不烧"


def classify_aod(value: float) -> str:
    """按 sunsetbot 历史数据反推的阈值生成 AOD 标签。"""
    if value >= 0.86:
        return "非常污"
    elif value >= 0.66:
        return "大污"
    elif value >= 0.585:
        return "污"
    elif value >= 0.45:
        return "小污"
    elif value >= 0.30:
        return "一般"
    elif value >= 0.20:
        return "还不错"
    return "水晶"


def score_sunset(
    cloud_low: list[float],
    cloud_mid: list[float],
    cloud_high: list[float],
    humidity: list[float],
) -> float:
    """根据日落前后各 1 小时的云层结构计算鲜艳度评分（0~1）。

    经典晚霞模型：
    - 中云（散射层）适量才有颜色，20%~70% 最佳
    - 低云过多挡住散射光，重罚
    - 高云/卷云（纹理层）适量加分
    - 湿度过高说明天空浑浊，轻微降分
    """
    if not cloud_low:
        return 0.0

    def avg(xs: list[float]) -> float:
        return sum(xs) / len(xs)

    low = avg(cloud_low)
    mid = avg(cloud_mid)
    high = avg(cloud_high)
    hum = avg(humidity)

    # 中云贡献：梯形，20% 以下没有散射介质，20~70% 满贡献，>85% 视为阴天降分
    if mid <= 20:
        mid_score = mid / 20 * 0.2
    elif mid <= 70:
        mid_score = 0.5 + (mid - 20) / 50 * 0.5
    elif mid <= 85:
        mid_score = 1.0 - (mid - 70) / 15 * 0.5
    else:
        mid_score = 0.5 - (mid - 85) / 15 * 0.5

    # 高云贡献：适量卷云加纹理，全覆盖减分
    if high <= 60:
        high_score = high / 60
    else:
        high_score = max(0.0, 1.0 - (high - 60) / 40 * 0.6)

    # 低云惩罚：>60% 低云基本挡光
    if low <= 40:
        low_factor = 1.0 - low / 40 * 0.3
    else:
        low_factor = max(0.0, 0.7 - (low - 40) / 60 * 0.7)

    # 湿度惩罚：>85% 天空浑浊
    hum_factor = 1.0 if hum <= 70 else max(0.5, 1.0 - (hum - 70) / 30 * 0.5)

    raw = (mid_score * 0.55 + high_score * 0.25 + (1.0 - abs(mid - 45) / 45) * 0.20) * low_factor * hum_factor
    return round(max(0.0, min(1.0, raw)), 3)


async def _fetch_json(url: str, params: dict) -> dict:
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            last_error = e
            import asyncio
            await asyncio.sleep(2 ** attempt)
    raise RuntimeError(f"Open-Meteo request failed after 3 attempts: {url}") from last_error


def _sunset_hour_estimate(d: date) -> tuple[int, int]:
    """粗估日落时间窗口（珠海全年日落 18:00~19:30，取日落前后各 1 小时）。"""
    # 简单按月份插值：6 月 19:10，12 月 17:55
    month = d.month
    if month in (5, 6, 7):
        sunset_h = 19
    elif month in (11, 12, 1):
        sunset_h = 18
    else:
        sunset_h = 18
    return max(0, sunset_h - WINDOW_BEFORE_H), sunset_h + WINDOW_AFTER_H


async def fetch_forecast(
    event: str = "set_1",
    model: str | None = None,
) -> OMSunsetForecast | None:
    """获取明日（set_2）或今日（set_1）的晚霞评分。

    Open-Meteo forecast_days 最多支持 16 天，set_2 用 tomorrow 参数即可。
    """
    tomorrow = event == "set_2"

    weather = await _fetch_json(WEATHER_URL, {
        "latitude": settings.latitude,
        "longitude": settings.longitude,
        "hourly": "cloud_cover_low,cloud_cover_mid,cloud_cover_high,relative_humidity_2m",
        "forecast_days": 2,
        "timezone": "Asia/Shanghai",
    })
    air = await _fetch_json(AIR_QUALITY_URL, {
        "latitude": settings.latitude,
        "longitude": settings.longitude,
        "hourly": "aerosol_optical_depth",
        "forecast_days": 2,
        "timezone": "Asia/Shanghai",
    })

    times: list[str] = weather["hourly"]["time"]
    today_str = datetime.now(HKT).date().isoformat()
    target_date_str = times[0][:10] if not tomorrow else None
    # 取目标日期：today（set_1）或 tomorrow（set_2）
    if tomorrow:
        dates = sorted({t[:10] for t in times})
        if len(dates) < 2:
            logger.warning("Open-Meteo returned only one day, cannot do set_2")
            return None
        target_date_str = dates[1]

    # 目标日期索引
    idx = [i for i, t in enumerate(times) if t[:10] == target_date_str]
    if not idx:
        logger.warning(f"No hourly data for {target_date_str}")
        return None

    target = date.fromisoformat(target_date_str)
    h_start, h_end = _sunset_hour_estimate(target)

    win = [i for i in idx if h_start <= int(times[i][11:13]) <= h_end]
    if not win:
        win = idx  # 兜底用全天数据

    def series(name: str, source: dict) -> list[float]:
        vals = source["hourly"].get(name, [])
        return [vals[i] for i in win if i < len(vals) and vals[i] is not None]

    cloud_low = series("cloud_cover_low", weather)
    cloud_mid = series("cloud_cover_mid", weather)
    cloud_high = series("cloud_cover_high", weather)
    humidity = series("relative_humidity_2m", weather)
    aod_series = series("aerosol_optical_depth", air)

    if not cloud_mid:
        logger.warning("No cloud_cover_mid data in sunset window")
        return None

    quality_value = score_sunset(cloud_low, cloud_mid, cloud_high, humidity)
    quality_label = classify_quality(quality_value)

    aod_value = round(sum(aod_series) / len(aod_series), 3) if aod_series else 0.0
    aod_label = classify_aod(aod_value)

    return OMSunsetForecast(
        city=settings.default_city,
        event_date=target,
        event_name="日落",
        quality_value=quality_value,
        quality_label=quality_label,
        quality_raw=f"{quality_value:.3f}（{quality_label}）",
        aod_value=aod_value,
        aod_label=aod_label,
        aod_raw=f"{aod_value:.3f}（{aod_label}）",
        model="OpenMeteo",
        image_url="",
        fetch_time=datetime.now(HKT),
    )
