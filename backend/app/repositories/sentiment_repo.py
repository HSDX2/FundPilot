"""Repository for market_sentiments table."""

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sentiment import MarketSentiment
from app.repositories.base import BaseRepository


class MarketSentimentRepo(BaseRepository[MarketSentiment]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(MarketSentiment, session)

    async def get_by_date(
        self, target_date: date,
    ) -> MarketSentiment | None:
        stmt = select(MarketSentiment).where(
            MarketSentiment.date == target_date,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def upsert(
        self, record: dict,
    ) -> MarketSentiment:
        """Insert or update sentiment for a date. Returns the record."""
        target_date = record.get("date")
        existing = await self.get_by_date(target_date)
        if existing:
            for key, value in record.items():
                if hasattr(existing, key) and value is not None:
                    setattr(existing, key, value)
            await self.session.flush()
            return existing
        obj = MarketSentiment(**record)
        self.session.add(obj)
        await self.session.flush()
        return obj
