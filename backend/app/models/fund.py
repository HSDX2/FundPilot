import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Fund(TimestampMixin, Base):
    __tablename__ = "funds"

    code: Mapped[str] = mapped_column(
        String(16), unique=True, nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str | None] = mapped_column(String(32))
    company: Mapped[str | None] = mapped_column(String(128))
    established_date: Mapped[date | None] = mapped_column(Date)
    scale: Mapped[float | None] = mapped_column(Numeric(20, 4))
    fund_manager: Mapped[str | None] = mapped_column(String(64))

    navs = relationship("FundNav", back_populates="fund", lazy="selectin")
    estimates = relationship("FundEstimate", back_populates="fund", lazy="selectin")


class FundNav(TimestampMixin, Base):
    __tablename__ = "fund_navs"

    fund_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("funds.id"), nullable=False
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    nav: Mapped[float | None] = mapped_column(Numeric(12, 4))
    accumulated_nav: Mapped[float | None] = mapped_column(Numeric(12, 4))
    daily_change_pct: Mapped[float | None] = mapped_column(Numeric(8, 4))

    fund = relationship("Fund", back_populates="navs")

    __table_args__ = (
        UniqueConstraint("fund_id", "date", name="uq_fund_nav_date"),
    )


class FundEstimate(TimestampMixin, Base):
    __tablename__ = "fund_estimates"

    fund_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("funds.id"), nullable=False
    )
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    estimate_nav: Mapped[float | None] = mapped_column(Numeric(12, 4))
    estimate_change_pct: Mapped[float | None] = mapped_column(Numeric(8, 4))
    estimate_change_amount: Mapped[float | None] = mapped_column(Numeric(8, 4))

    fund = relationship("Fund", back_populates="estimates")

    __table_args__ = (
        UniqueConstraint("fund_id", "timestamp", name="uq_fund_estimate_ts"),
    )
