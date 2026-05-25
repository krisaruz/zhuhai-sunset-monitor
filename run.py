import json
import logging
import asyncio
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s"
)
logger = logging.getLogger("sunset-runner")

# Import project modules
from src.config import settings
from src.services.sunsetbot import fetch_forecast
from src.services.astronomer import compute_sunset_azimuth, compute_sun_path
from src.services.location_recommender import recommend_locations
from src.services.notifier import send_feishu_notification
from src.models.location import ShootingLocation
from src.seed_locations import LOCATIONS


async def process_forecast(event_type: str, target_date: date) -> dict | None:
    """Fetch forecast for event_type, compute metadata, and return record dict."""
    logger.info(f"Processing forecast for event={event_type}, date={target_date}...")
    
    forecast = await fetch_forecast(event=event_type, model=settings.sunsetbot_model)
    if not forecast:
        logger.warning(f"No forecast found for event {event_type}")
        return None
        
    # Verify the date matches what we expected (or use whatever the forecast returned)
    event_date = forecast.event_date
    
    # Compute sunset azimuth & time
    azimuth, sunset_time = compute_sunset_azimuth(
        settings.latitude, settings.longitude, event_date
    )
    
    record = {
        "city": settings.default_city,
        "event_date": str(event_date),
        "event_time": sunset_time.strftime("%H:%M"),
        "event_type": event_type,
        "model": settings.sunsetbot_model,
        "quality_value": forecast.quality_value,
        "quality_label": forecast.quality_label,
        "quality_raw": forecast.quality_raw,
        "aod_value": forecast.aod_value,
        "aod_label": forecast.aod_label,
        "aod_raw": forecast.aod_raw,
        "image_url": forecast.image_url,
        "sunset_azimuth": round(azimuth, 1),
        "fetch_time": datetime.now(timezone(timedelta(hours=8))).isoformat(),
        "notified": False,
    }
    
    return record


async def main():
    # Setup directories
    Path("data").mkdir(exist_ok=True)
    
    # Define local time in HKT (UTC+8)
    hkt_tz = timezone(timedelta(hours=8))
    now_hkt = datetime.now(hkt_tz)
    today_date = now_hkt.date()
    tomorrow_date = today_date + timedelta(days=1)
    
    logger.info(f"Running script. Local HKT Time: {now_hkt.isoformat()}, Hour: {now_hkt.hour}")
    
    # 1. Load existing history.json
    history_file = Path("data/history.json")
    history = []
    if history_file.exists():
        try:
            with open(history_file, "r", encoding="utf-8") as f:
                history = json.load(f)
            logger.info(f"Loaded {len(history)} records from history.json")
        except Exception as e:
            logger.error(f"Error loading history.json: {e}. Starting fresh.")
            
    # Helper to find a record in history list
    def find_record_idx(date_str: str, ev_type: str):
        return next(
            (i for i, r in enumerate(history) if r.get("event_date") == date_str and r.get("event_type") == ev_type),
            None
        )

    # 2. Fetch today's sunset forecast (set_1)
    today_record = await process_forecast("set_1", today_date)
    if today_record:
        # Check if we already had a notified record for this
        idx = find_record_idx(today_record["event_date"], "set_1")
        if idx is not None:
            today_record["notified"] = history[idx].get("notified", False)
            
        # Update or append
        if idx is not None:
            history[idx] = today_record
        else:
            history.append(today_record)
            
    # 3. Fetch tomorrow's sunset forecast (set_2)
    tomorrow_record = await process_forecast("set_2", tomorrow_date)
    if tomorrow_record:
        # Check if we already had a notified record for this
        idx = find_record_idx(tomorrow_record["event_date"], "set_2")
        if idx is not None:
            tomorrow_record["notified"] = history[idx].get("notified", False)
            
        # Update or append
        if idx is not None:
            history[idx] = tomorrow_record
        else:
            history.append(tomorrow_record)

    # 4. Check Feishu Notifications
    # We only notify for sunsets (set_1 or set_2) if they qualify.
    # Typically we run cron at 12:05 and 17:05, which will process set_1 (today's sunset).
    # If it's afternoon or quality is good, send.
    for record in [today_record, tomorrow_record]:
        if not record:
            continue
            
        # If notification threshold met and not notified yet
        already_notified = record.get("notified", False)
        quality = record["quality_value"]
        
        # Check if we should notify
        should_notify = (
            quality >= settings.notify_min_quality
            and not already_notified
        )
        
        # Or if quality improved significantly (> 0.1) from previous notification
        # (Find historical notified record for same date and event type)
        idx = find_record_idx(record["event_date"], record["event_type"])
        if idx is not None and history[idx].get("notified", False):
            prev_quality = history[idx].get("quality_value", 0.0)
            if quality - prev_quality > 0.1:
                should_notify = True
                logger.info(f"Significant quality improvement ({prev_quality:.3f} -> {quality:.3f}) for {record['event_date']}. Re-notifying.")

        if should_notify:
            if settings.feishu_webhook_url:
                logger.info(f"Quality ({quality:.3f}) matches criteria for {record['event_date']}. Preparing notification...")
                
                # Mock forecast object for notifier (which expects a schema/dataclass)
                # We can construct a simple class to act as the forecast object
                class TempForecast:
                    def __init__(self, d):
                        for k, v in d.items():
                            setattr(self, k, v)
                
                # Create ShootingLocation mock list for recommender
                locations = [ShootingLocation(active=True, **loc) for loc in LOCATIONS]
                
                # Re-compute azimuth and sunset_time datetime object
                event_date_obj = date.fromisoformat(record["event_date"])
                azimuth, sunset_time = compute_sunset_azimuth(
                    settings.latitude, settings.longitude, event_date_obj
                )
                
                # Get recommendations
                recs = recommend_locations(azimuth, sunset_time, locations)
                
                # Format forecast object properties needed by build_card_message
                forecast_obj = TempForecast(record)
                forecast_obj.event_name = "日落"  # or read it dynamically
                
                # Send
                success = await send_feishu_notification(forecast_obj, recs)
                if success:
                    record["notified"] = True
                    # Update in history
                    idx = find_record_idx(record["event_date"], record["event_type"])
                    if idx is not None:
                        history[idx]["notified"] = True
                    logger.info(f"Feishu notification sent successfully for {record['event_date']}")
                else:
                    logger.error(f"Failed to send Feishu notification for {record['event_date']}")
            else:
                logger.warning("Feishu webhook URL not configured. Skipping notification.")

    # 5. Clean up & sort history
    # Sort by event_date descending, then event_type descending (set_2 before set_1 for same date if any, but date is unique generally)
    history.sort(key=lambda r: (r.get("event_date", ""), r.get("event_type", "")), reverse=True)
    history = history[:100]  # limit to 100 entries
    
    # Save history.json
    with open(history_file, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
    logger.info("Saved data/history.json")

    # 6. Generate data/map-data.json for frontend
    # If current HKT hour >= 20 (8 PM), we show tomorrow's sunset. Else we show today's.
    target_show_date = tomorrow_date if now_hkt.hour >= 20 else today_date
    target_event_type = "set_2" if now_hkt.hour >= 20 else "set_1"
    
    logger.info(f"Frontend map-data target date: {target_show_date} ({target_event_type})")
    
    # Get the record from history
    rec_idx = find_record_idx(str(target_show_date), target_event_type)
    active_record = history[rec_idx] if rec_idx is not None else None
    
    # If we couldn't find the record, fallback to the latest set_1 or set_2 in history
    if not active_record and len(history) > 0:
        active_record = history[0]
        logger.warning(f"Could not find exact record for {target_show_date} ({target_event_type}). Falling back to latest record: {active_record.get('event_date')}")
        
    if active_record:
        rec_date = date.fromisoformat(active_record["event_date"])
        azimuth, sunset_time = compute_sunset_azimuth(
            settings.latitude, settings.longitude, rec_date
        )
        sun_path = compute_sun_path(settings.latitude, settings.longitude, rec_date)
        locations = [ShootingLocation(active=True, **loc) for loc in LOCATIONS]
        recs = recommend_locations(azimuth, sunset_time, locations)
        
        loc_data = []
        for rec in recs:
            matching_loc = next((l for l in LOCATIONS if l["name"] == rec.name), None)
            facing_min = matching_loc["facing_azimuth_min"] if matching_loc else 0
            facing_max = matching_loc["facing_azimuth_max"] if matching_loc else 0
            loc_data.append({
                "name": rec.name,
                "lat": rec.lat,
                "lon": rec.lon,
                "facing_min": facing_min,
                "facing_max": facing_max,
                "score": rec.score,
                "reason": rec.reason,
                "tags": rec.tags,
                "description": rec.description,
                "suggested_arrival": rec.suggested_arrival,
                "map_url": rec.map_url,
            })
            
        map_data = {
            "center": {"lat": settings.latitude, "lon": settings.longitude},
            "date": str(rec_date),
            "sunset": {
                "azimuth": round(azimuth, 1),
                "time": sunset_time.strftime("%H:%M"),
                "quality_value": active_record.get("quality_value"),
                "quality_label": active_record.get("quality_label"),
                "aod_value": active_record.get("aod_value"),
                "aod_label": active_record.get("aod_label"),
                "image_url": active_record.get("image_url"),
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
        
        map_data_file = Path("data/map-data.json")
        with open(map_data_file, "w", encoding="utf-8") as f:
            json.dump(map_data, f, ensure_ascii=False, indent=2)
        logger.info("Saved data/map-data.json")
    else:
        logger.error("No record found in history to generate map-data.json")


if __name__ == "__main__":
    asyncio.run(main())
