"""Market sentiment model — daily aggregated sentiment indicators."""

from datetime import date

from sqlalchemy import Date, Numeric
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class MarketSentiment(TimestampMixin, Base):
    __tablename__ = "market_sentiments"

    date: Mapped[date] = mapped_column(
        Date, nullable=False, unique=True, index=True,
    )
    limit_up_count: Mapped[int | None] = mapped_column(Numeric(6, 0))
    limit_down_count: Mapped[int | None] = mapped_column(Numeric(6, 0))
    limit_up_broken_count: Mapped[int | None] = mapped_column(Numeric(6, 0))
    consecutive_limit_up_count: Mapped[int | None] = mapped_column(Numeric(6, 0))
    north_bound_net_inflow: Mapped[float | None] = mapped_column(Numeric(20, 4))
    margin_balance_sse: Mapped[float | None] = mapped_column(Numeric(20, 4))
    margin_balance_szse: Mapped[float | None] = mapped_column(Numeric(20, 4))
    lhb_stock_count: Mapped[int | None] = mapped_column(Numeric(6, 0))
    advance_count: Mapped[int | None] = mapped_column(Numeric(6, 0))
    decline_count: Mapped[int | None] = mapped_column(Numeric(6, 0))
    market_total_cap: Mapped[float | None] = mapped_column(Numeric(20, 4))
    composite_sentiment_score: Mapped[float | None] = mapped_column(Numeric(6, 2))
    extra: Mapped[dict | None] = mapped_column(JSONB)
