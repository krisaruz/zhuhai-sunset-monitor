import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta

import ephem


def compute_sunset_azimuth(
    lat: float, lon: float, target_date: date
) -> tuple[float, datetime]:
    """
    Compute sunset azimuth and time for given coordinates and date.

    Returns:
        (azimuth_degrees, sunset_local_datetime)
        Azimuth: 0=North, 90=East, 180=South, 270=West
    """
    observer = ephem.Observer()
    observer.lat = str(lat)
    observer.lon = str(lon)
    observer.elevation = 0
    observer.pressure = 0  # disable atmospheric refraction for azimuth

    observer.date = target_date.isoformat()

    sun = ephem.Sun()
    sunset_utc = observer.next_setting(sun)

    observer.date = sunset_utc
    sun.compute(observer)

    azimuth_deg = float(sun.az) * 180.0 / ephem.pi
    sunset_local = ephem.Date(sunset_utc + 8 * ephem.hour)  # UTC+8

    return azimuth_deg, sunset_local.datetime()


@dataclass(frozen=True)
class SunPathPoint:
    lat: float
    lon: float
    azimuth: float
    altitude: float
    time: str  # HH:MM
    color: str  # hex color for gradient


def compute_sun_path(
    lat: float, lon: float, target_date: date, interval_minutes: int = 30
) -> list[SunPathPoint]:
    """Compute sun azimuth/altitude at regular intervals from sunrise to sunset."""
    observer = ephem.Observer()
    observer.lat = str(lat)
    observer.lon = str(lon)
    observer.elevation = 0
    observer.pressure = 0

    # Set to previous day 16:00 UTC = target date 00:00 local (UTC+8)
    prev_day = target_date - timedelta(days=1)
    observer.date = f"{prev_day.isoformat()} 16:00:00"
    sun = ephem.Sun()

    sunrise_utc = observer.next_rising(sun)
    sunset_utc = observer.next_setting(sun)

    points: list[SunPathPoint] = []
    step = interval_minutes / (24.0 * 60.0)  # fraction of a day
    t = sunrise_utc
    total_steps = int((sunset_utc - sunrise_utc) / step)

    for i in range(total_steps + 1):
        observer.date = t
        sun.compute(observer)

        azimuth_deg = float(sun.az) * 180.0 / ephem.pi
        altitude_deg = float(sun.alt) * 180.0 / ephem.pi

        if altitude_deg < -2:  # skip below horizon
            t += step
            continue

        local_dt = ephem.Date(t + 8 * ephem.hour)
        dt = local_dt.datetime()

        # Color gradient: morning gold (#FFD700) -> evening orange-red (#FF4500)
        progress = i / max(total_steps, 1)
        g = int(215 - progress * 145)  # 215 -> 70
        color = f"#ff{g:02x}00"

        # Project sun position onto ground (approximate)
        # Use a fixed radius offset from observer center

        radius_km = 3.0
        az_rad = math.radians(azimuth_deg)
        offset_lat = lat + (radius_km / 111.0) * math.cos(az_rad)
        offset_lon = lon + (radius_km / (111.0 * math.cos(math.radians(lat)))) * math.sin(az_rad)

        points.append(SunPathPoint(
            lat=round(offset_lat, 6),
            lon=round(offset_lon, 6),
            azimuth=round(azimuth_deg, 1),
            altitude=round(altitude_deg, 1),
            time=dt.strftime("%H:%M"),
            color=color,
        ))
        t += step

    return points


def get_season(target_date: date) -> str:
    """Return season name for a date (Northern Hemisphere)."""
    month = target_date.month
    if month in (3, 4, 5):
        return "spring"
    elif month in (6, 7, 8):
        return "summer"
    elif month in (9, 10, 11):
        return "autumn"
    else:
        return "winter"
