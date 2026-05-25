from datetime import date

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.models.database import get_db
from src.models.sunset import SunsetRecord
from src.services.astronomer import compute_sunset_azimuth

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, db: AsyncSession = Depends(get_db)):
    today = date.today()
    azimuth, sunset_time = compute_sunset_azimuth(
        settings.latitude, settings.longitude, today
    )

    # Get latest forecast for today
    stmt = (
        select(SunsetRecord)
        .where(SunsetRecord.event_date == today, SunsetRecord.event_type.like("set%"))
        .order_by(SunsetRecord.fetch_time.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    record = result.scalar_one_or_none()

    # Get recent history for chart
    from sqlalchemy import func
    stmt_history = (
        select(SunsetRecord)
        .where(SunsetRecord.event_type.like("set%"), SunsetRecord.quality_value.is_not(None))
        .order_by(SunsetRecord.event_date.desc())
        .limit(30)
    )
    result_history = await db.execute(stmt_history)
    history = list(reversed(result_history.scalars().all()))

    context = {
        "request": request,
        "record": record,
        "sunset_time": sunset_time.strftime("%H:%M"),
        "sunset_azimuth": round(azimuth, 1),
        "today": str(today),
        "history": history,
        "amap_key": settings.amap_key,
    }
    return templates.TemplateResponse(request, "dashboard.html", context)
