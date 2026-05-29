import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class AnalysisReport(TimestampMixin, Base):
    __tablename__ = "analysis_reports"

    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    report_type: Mapped[str] = mapped_column(String(16), nullable=False)
    category: Mapped[str | None] = mapped_column(
        String(16), nullable=True, index=True
    )
    sector_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sectors.id"), nullable=True
    )
    content: Mapped[dict] = mapped_column(JSONB, nullable=False)
    ai_model: Mapped[str | None] = mapped_column(String(64))


class Recommendation(TimestampMixin, Base):
    """AI 推荐结果."""

    __tablename__ = "recommendations"

    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    mode: Mapped[str | None] = mapped_column(String(16))
    rec_type: Mapped[str] = mapped_column(String(16), nullable=False)
    action: Mapped[str] = mapped_column(String(16), nullable=False)
    target_name: Mapped[str] = mapped_column(String(128), nullable=False)
    target_code: Mapped[str | None] = mapped_column(String(32))
    confidence: Mapped[int] = mapped_column(Numeric(3), default=50)
    reason_summary: Mapped[str] = mapped_column(String(512), default="")
    reason_detail: Mapped[dict | None] = mapped_column(JSONB)
    risk_warning: Mapped[str | None] = mapped_column(String(256))
    source_data: Mapped[dict | None] = mapped_column(JSONB)


class FundAdvice(TimestampMixin, Base):
    __tablename__ = "fund_advices"

    fund_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("funds.id"), nullable=False
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    action: Mapped[str] = mapped_column(String(16), nullable=False)
    reason: Mapped[dict] = mapped_column(JSONB, nullable=False)
    confidence: Mapped[float | None] = mapped_column(Numeric(4, 2))
    ai_model: Mapped[str | None] = mapped_column(String(64))
