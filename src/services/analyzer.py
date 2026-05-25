from dataclasses import dataclass
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.sunset import SunsetRecord


@dataclass(frozen=True)
class MonthlyAnalysis:
    period: str
    avg_quality: float
    max_quality: float
    best_date: str | None
    record_count: int
    burn_distribution: dict[str, int]


def _classify_burn(value: float) -> str:
    if value >= 0.5:
        return "大烧"
    elif value >= 0.2:
        return "中烧"
    elif value >= 0.05:
        return "小烧"
    elif value >= 0.01:
        return "微烧"
    return "不烧"


async def get_monthly_analysis(
    db: AsyncSession, year: int, month: int
) -> MonthlyAnalysis:
    """Analyze sunset quality for a specific month."""
    from sqlalchemy import extract

    stmt = (
        select(SunsetRecord)
        .where(
            extract("year", SunsetRecord.event_date) == year,
            extract("month", SunsetRecord.event_date) == month,
            SunsetRecord.quality_value.is_not(None),
            SunsetRecord.event_type.like("set%"),
        )
        .order_by(SunsetRecord.event_date)
    )
    result = await db.execute(stmt)
    records = result.scalars().all()

    if not records:
        return MonthlyAnalysis(
            period=f"{year}-{month:02d}",
            avg_quality=0.0,
            max_quality=0.0,
            best_date=None,
            record_count=0,
            burn_distribution={},
        )

    qualities = [r.quality_value for r in records if r.quality_value is not None]
    avg_q = sum(qualities) / len(qualities) if qualities else 0.0
    max_q = max(qualities) if qualities else 0.0

    best_record = max(records, key=lambda r: r.quality_value or 0)

    burn_dist: dict[str, int] = {}
    for q in qualities:
        label = _classify_burn(q)
        burn_dist[label] = burn_dist.get(label, 0) + 1

    return MonthlyAnalysis(
        period=f"{year}-{month:02d}",
        avg_quality=round(avg_q, 4),
        max_quality=round(max_q, 4),
        best_date=str(best_record.event_date),
        record_count=len(records),
        burn_distribution=burn_dist,
    )


async def get_best_dates(
    db: AsyncSession, top_n: int = 10
) -> list[dict]:
    """Get top N best sunset dates on record."""
    stmt = (
        select(SunsetRecord)
        .where(
            SunsetRecord.quality_value.is_not(None),
            SunsetRecord.event_type.like("set%"),
        )
        .order_by(SunsetRecord.quality_value.desc())
        .limit(top_n)
    )
    result = await db.execute(stmt)
    records = result.scalars().all()

    return [
        {
            "date": str(r.event_date),
            "quality_value": r.quality_value,
            "quality_label": r.quality_label,
            "aod_value": r.aod_value,
            "aod_label": r.aod_label,
        }
        for r in records
    ]
