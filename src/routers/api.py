from datetime import date, datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.models.database import get_db
from src.models.sunset import SunsetRecord
from src.models.location import ShootingLocation
from src.services.astronomer import compute_sunset_azimuth, compute_sun_path
from src.services.location_recommender import recommend_locations
from src.services.analyzer import get_monthly_analysis, get_best_dates
from src.services.location_recommender import LocationRecommendation
from src.tasks.scheduler import fetch_and_notify

router = APIRouter(prefix="/api")


@router.get("/forecast/today")
async def forecast_today(db: AsyncSession = Depends(get_db)):
    today = date.today()
    stmt = (
        select(SunsetRecord)
        .where(SunsetRecord.event_date == today, SunsetRecord.event_type.like("set%"))
        .order_by(SunsetRecord.fetch_time.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    record = result.scalar_one_or_none()
    if record is None:
        return {"status": "no_data", "message": "今日暂无预报数据，请稍后再试"}
    return _record_to_dict(record)


@router.get("/forecast/tomorrow")
async def forecast_tomorrow(db: AsyncSession = Depends(get_db)):
    from datetime import timedelta
    tomorrow = date.today() + timedelta(days=1)
    stmt = (
        select(SunsetRecord)
        .where(SunsetRecord.event_date == tomorrow, SunsetRecord.event_type.like("set%"))
        .order_by(SunsetRecord.fetch_time.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    record = result.scalar_one_or_none()
    if record is None:
        return {"status": "no_data", "message": "明日暂无预报数据"}
    return _record_to_dict(record)


@router.get("/forecast/{target_date}")
async def forecast_by_date(target_date: str, db: AsyncSession = Depends(get_db)):
    d = date.fromisoformat(target_date)
    stmt = (
        select(SunsetRecord)
        .where(SunsetRecord.event_date == d, SunsetRecord.event_type.like("set%"))
        .order_by(SunsetRecord.fetch_time.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    record = result.scalar_one_or_none()
    if record is None:
        return {"status": "no_data", "message": f"{target_date} 暂无预报数据"}
    return _record_to_dict(record)


@router.get("/history")
async def history(
    start_date: str | None = None,
    end_date: str | None = None,
    min_quality: float | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(SunsetRecord).where(SunsetRecord.event_type.like("set%"))

    if start_date:
        stmt = stmt.where(SunsetRecord.event_date >= date.fromisoformat(start_date))
    if end_date:
        stmt = stmt.where(SunsetRecord.event_date <= date.fromisoformat(end_date))
    if min_quality is not None:
        stmt = stmt.where(SunsetRecord.quality_value >= min_quality)

    stmt = stmt.order_by(SunsetRecord.event_date.desc())
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(stmt)
    records = result.scalars().all()

    return {
        "page": page,
        "page_size": page_size,
        "records": [_record_to_dict(r) for r in records],
    }


@router.get("/history/best")
async def best_dates(top_n: int = Query(10, ge=1, le=50), db: AsyncSession = Depends(get_db)):
    return await get_best_dates(db, top_n)


@router.get("/analysis/monthly")
async def analysis_monthly(
    year: int | None = None,
    month: int | None = None,
    db: AsyncSession = Depends(get_db),
):
    now = datetime.now()
    y = year or now.year
    m = month or now.month
    result = await get_monthly_analysis(db, y, m)
    return {
        "period": result.period,
        "avg_quality": result.avg_quality,
        "max_quality": result.max_quality,
        "best_date": result.best_date,
        "record_count": result.record_count,
        "burn_distribution": result.burn_distribution,
    }


@router.get("/locations")
async def list_locations(db: AsyncSession = Depends(get_db)):
    stmt = select(ShootingLocation).where(ShootingLocation.active == True)
    result = await db.execute(stmt)
    locations = result.scalars().all()
    return [
        {
            "id": loc.id,
            "name": loc.name,
            "lat": loc.lat,
            "lon": loc.lon,
            "facing_azimuth_min": loc.facing_azimuth_min,
            "facing_azimuth_max": loc.facing_azimuth_max,
            "description": loc.description,
            "best_seasons": loc.best_seasons,
            "tags": loc.tags,
            "map_url": loc.map_url,
        }
        for loc in locations
    ]


@router.get("/locations/recommend")
async def recommend(
    target_date: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    d = date.fromisoformat(target_date) if target_date else date.today()
    azimuth, sunset_time = compute_sunset_azimuth(settings.latitude, settings.longitude, d)

    stmt = select(ShootingLocation).where(ShootingLocation.active == True)
    result = await db.execute(stmt)
    locations = list(result.scalars().all())

    recs = recommend_locations(azimuth, sunset_time, locations)
    return {
        "sunset_azimuth": round(azimuth, 1),
        "sunset_time": sunset_time.isoformat(),
        "date": str(d),
        "recommendations": [
            {
                "name": r.name,
                "lat": r.lat,
                "lon": r.lon,
                "facing_azimuth": r.facing_azimuth,
                "description": r.description,
                "tags": r.tags,
                "map_url": r.map_url,
                "score": r.score,
                "reason": r.reason,
                "suggested_arrival": r.suggested_arrival,
            }
            for r in recs
        ],
    }


@router.post("/forecast/fetch")
async def manual_fetch(event: str = "set_1", model: str = "EC"):
    """Manually trigger a forecast fetch."""
    await fetch_and_notify(event=event, model=model)
    return {"status": "ok", "message": f"Fetch triggered: event={event}, model={model}"}


@router.get("/map-data")
async def map_data(
    target_date: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Return all data needed for the map visualization."""
    d = date.fromisoformat(target_date) if target_date else date.today()
    azimuth, sunset_time = compute_sunset_azimuth(settings.latitude, settings.longitude, d)

    # Get latest forecast
    stmt = (
        select(SunsetRecord)
        .where(SunsetRecord.event_date == d, SunsetRecord.event_type.like("set%"))
        .order_by(SunsetRecord.fetch_time.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    record = result.scalar_one_or_none()

    # Get locations with recommendations
    stmt_loc = select(ShootingLocation).where(ShootingLocation.active == True)
    result_loc = await db.execute(stmt_loc)
    locations = list(result_loc.scalars().all())

    recs = recommend_locations(azimuth, sunset_time, locations)

    # Build location data with scores
    loc_data = []
    for rec in recs:
        loc_data.append({
            "name": rec.name,
            "lat": rec.lat,
            "lon": rec.lon,
            "facing_min": next(
                (l.facing_azimuth_min for l in locations if l.name == rec.name), 0
            ),
            "facing_max": next(
                (l.facing_azimuth_max for l in locations if l.name == rec.name), 0
            ),
            "score": rec.score,
            "reason": rec.reason,
            "tags": rec.tags,
            "description": rec.description,
            "suggested_arrival": rec.suggested_arrival,
            "map_url": rec.map_url,
        })

    # Compute sun path
    sun_path = compute_sun_path(settings.latitude, settings.longitude, d)

    return {
        "center": {"lat": settings.latitude, "lon": settings.longitude},
        "date": str(d),
        "sunset": {
            "azimuth": round(azimuth, 1),
            "time": sunset_time.strftime("%H:%M"),
            "quality_value": record.quality_value if record else None,
            "quality_label": record.quality_label if record else None,
            "aod_value": record.aod_value if record else None,
            "aod_label": record.aod_label if record else None,
        },
        "locations": loc_data,
        "sun_path": [
            {
                "lat": p.lat,
                "lon": p.lon,
                "azimuth": p.azimuth,
                "altitude": p.altitude,
                "time": p.time,
                "color": p.color,
            }
            for p in sun_path
        ],
    }


def _record_to_dict(r: SunsetRecord) -> dict:
    return {
        "id": r.id,
        "city": r.city,
        "event_date": str(r.event_date),
        "event_time": r.event_time.isoformat() if r.event_time else None,
        "event_type": r.event_type,
        "model": r.model,
        "quality_value": r.quality_value,
        "quality_label": r.quality_label,
        "quality_raw": r.quality_raw,
        "aod_value": r.aod_value,
        "aod_label": r.aod_label,
        "aod_raw": r.aod_raw,
        "image_url": r.image_url,
        "sunset_azimuth": r.sunset_azimuth,
        "fetch_time": r.fetch_time.isoformat() if r.fetch_time else None,
        "notified": r.notified,
    }
