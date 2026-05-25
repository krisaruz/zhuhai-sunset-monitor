import logging
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select

from src.config import settings
from src.models.database import async_session
from src.models.sunset import SunsetRecord
from src.models.location import ShootingLocation, NotificationLog
from src.services.sunsetbot import fetch_forecast
from src.services.astronomer import compute_sunset_azimuth
from src.services.location_recommender import recommend_locations
from src.services.notifier import send_feishu_notification

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()


async def fetch_and_notify(event: str = "set_1", model: str = "EC") -> None:
    """Core pipeline: fetch -> parse -> store -> notify if threshold met."""
    logger.info(f"Fetching forecast: event={event}, model={model}")

    forecast = await fetch_forecast(event=event, model=model)
    if forecast is None:
        logger.warning("Failed to fetch forecast or no data available")
        return

    # Compute sunset azimuth
    azimuth, sunset_time = compute_sunset_azimuth(
        settings.latitude, settings.longitude, forecast.event_date
    )

    # Store in database
    async with async_session() as db:
        # Upsert: check if record exists
        stmt = select(SunsetRecord).where(
            SunsetRecord.city == settings.default_city,
            SunsetRecord.event_date == forecast.event_date,
            SunsetRecord.event_type == event,
            SunsetRecord.model == model,
        )
        result = await db.execute(stmt)
        record = result.scalar_one_or_none()

        if record is None:
            record = SunsetRecord(
                city=settings.default_city,
                event_date=forecast.event_date,
                event_time=sunset_time,
                event_type=event,
                model=model,
                quality_value=forecast.quality_value,
                quality_label=forecast.quality_label,
                quality_raw=forecast.quality_raw,
                aod_value=forecast.aod_value,
                aod_label=forecast.aod_label,
                aod_raw=forecast.aod_raw,
                image_url=forecast.image_url,
                sunset_azimuth=azimuth,
                fetch_time=forecast.fetch_time,
            )
            db.add(record)
        else:
            record.quality_value = forecast.quality_value
            record.quality_label = forecast.quality_label
            record.quality_raw = forecast.quality_raw
            record.aod_value = forecast.aod_value
            record.aod_label = forecast.aod_label
            record.aod_raw = forecast.aod_raw
            record.image_url = forecast.image_url
            record.sunset_azimuth = azimuth
            record.event_time = sunset_time
            record.fetch_time = forecast.fetch_time

        await db.commit()
        await db.refresh(record)
        record_id = record.id

        # Check notification conditions
        should_notify = (
            forecast.quality_value >= settings.notify_min_quality
            and not record.notified
            and event.startswith("set")  # Only notify for sunsets
        )

        # Re-notify if quality improved significantly
        if record.notified and forecast.quality_value >= settings.notify_min_quality:
            # Check if quality improved by > 0.1 from what we last notified about
            prev_quality = record.quality_value or 0
            if forecast.quality_value - prev_quality > 0.1:
                should_notify = True
                logger.info(f"Quality improved significantly, re-notifying")

        if should_notify:
            # Get location recommendations
            stmt_loc = select(ShootingLocation).where(ShootingLocation.active == True)
            result_loc = await db.execute(stmt_loc)
            locations = result_loc.scalars().all()

            recommendations = recommend_locations(
                sunset_azimuth=azimuth,
                sunset_time=sunset_time,
                all_locations=list(locations),
            )

            # Send notification
            success = await send_feishu_notification(forecast, recommendations)

            # Log notification
            log = NotificationLog(
                record_id=record_id,
                channel="feishu",
                status="sent" if success else "failed",
                sent_at=datetime.now().isoformat(),
            )
            db.add(log)

            if success:
                record.notified = True
                record.notified_at = datetime.now()
                logger.info(f"Notification sent for {forecast.event_date} {event}")
            else:
                logger.warning(f"Failed to send notification for {forecast.event_date}")

            await db.commit()

    logger.info(f"Done: {forecast.event_date} {event} quality={forecast.quality_value}")


def setup_scheduler() -> None:
    """Configure and start the APScheduler."""
    # Morning fetch: today's sunset (EC model)
    scheduler.add_job(
        fetch_and_notify,
        CronTrigger(hour=6, minute=0),
        kwargs={"event": "set_1", "model": "EC"},
        id="morning_sunset_ec",
        name="Morning sunset forecast (EC)",
    )

    # Morning fetch: GFS model for comparison
    scheduler.add_job(
        fetch_and_notify,
        CronTrigger(hour=7, minute=0),
        kwargs={"event": "set_1", "model": "GFS"},
        id="morning_sunset_gfs",
        name="Morning sunset forecast (GFS)",
    )

    # Afternoon update: fresher model data
    scheduler.add_job(
        fetch_and_notify,
        CronTrigger(hour=16, minute=0),
        kwargs={"event": "set_1", "model": "EC"},
        id="afternoon_sunset_ec",
        name="Afternoon sunset update (EC)",
    )

    # Evening: tomorrow's forecast
    scheduler.add_job(
        fetch_and_notify,
        CronTrigger(hour=20, minute=0),
        kwargs={"event": "set_2", "model": "EC"},
        id="tomorrow_sunset_ec",
        name="Tomorrow sunset forecast (EC)",
    )

    scheduler.start()
    logger.info("Scheduler started with 4 jobs")
