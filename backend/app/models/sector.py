import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Sector(TimestampMixin, Base):
    __tablename__ = "sectors"

    name: Mapped[str] = mapped_column(String(64), nullable=False)
    code: Mapped[str | None] = mapped_column(String(32), unique=True)
    category: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(String)

    snapshots = relationship("SectorSnapshot", back_populates="sector", lazy="selectin")
    money_flows = relationship(
        "SectorMoneyFlow", back_populates="sector", lazy="selectin"
    )


class SectorSnapshot(TimestampMixin, Base):
    __tablename__ = "sector_snapshots"

    sector_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sectors.id"), nullable=False
    )
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    price: Mapped[float | None] = mapped_column(Numeric(14, 4))
    open: Mapped[float | None] = mapped_column(Numeric(14, 4))
    high: Mapped[float | None] = mapped_column(Numeric(14, 4))
    low: Mapped[float | None] = mapped_column(Numeric(14, 4))
    change_pct: Mapped[float | None] = mapped_column(Numeric(8, 4))
    volume: Mapped[int | None] = mapped_column(Numeric(20, 0))
    turnover: Mapped[float | None] = mapped_column(Numeric(20, 4))

    sector = relationship("Sector", back_populates="snapshots")

    __table_args__ = (
        UniqueConstraint("sector_id", "timestamp", name="uq_sector_snapshot_ts"),
    )


class SectorMoneyFlow(TimestampMixin, Base):
    __tablename__ = "sector_money_flows"

    sector_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sectors.id"), nullable=False
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    main_force_net_inflow: Mapped[float | None] = mapped_column(Numeric(20, 4))
    retail_net_inflow: Mapped[float | None] = mapped_column(Numeric(20, 4))
    middle_net_inflow: Mapped[float | None] = mapped_column(Numeric(20, 4))

    sector = relationship("Sector", back_populates="money_flows")

    __table_args__ = (
        UniqueConstraint("sector_id", "date", name="uq_sector_money_flow_date"),
    )
