from datetime import datetime

from sqlalchemy import Boolean, Date, DateTime, Float, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.models.database import Base


class SunsetRecord(Base):
    __tablename__ = "sunset_records"
    __table_args__ = (
        UniqueConstraint("city", "event_date", "event_type", "model", name="uq_sunset_record"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    city: Mapped[str] = mapped_column(String(50), default="珠海")
    event_date: Mapped[str] = mapped_column(Date)
    event_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    event_type: Mapped[str] = mapped_column(String(10))  # set_1, set_2, rise_1, rise_2
    model: Mapped[str] = mapped_column(String(10))  # EC, GFS

    quality_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    quality_label: Mapped[str | None] = mapped_column(String(20), nullable=True)
    quality_raw: Mapped[str | None] = mapped_column(String(100), nullable=True)

    aod_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    aod_label: Mapped[str | None] = mapped_column(String(20), nullable=True)
    aod_raw: Mapped[str | None] = mapped_column(String(100), nullable=True)

    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    sunset_azimuth: Mapped[float | None] = mapped_column(Float, nullable=True)

    fetch_time: Mapped[datetime] = mapped_column(DateTime)
    raw_response: Mapped[str | None] = mapped_column(Text, nullable=True)

    notified: Mapped[bool] = mapped_column(Boolean, default=False)
    notified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
