"""Repository for market_sentiments table."""

from datetime import date

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sentiment import MarketSentiment
from app.repositories.base import BaseRepository


class MarketSentimentRepo(BaseRepository[MarketSentiment]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, MarketSentiment)

    async def get_by_date(
        self, target_date: date,
    ) -> MarketSentiment | None:
        stmt = select(MarketSentiment).where(
            MarketSentiment.date == target_date,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list(
        self, skip: int = 0, limit: int = 20, **filters,
    ) -> list[MarketSentiment]:
        stmt = select(MarketSentiment)
        for key, value in filters.items():
            if value is not None:
                column = getattr(MarketSentiment, key, None)
                if column is not None:
                    stmt = stmt.where(column == value)
        stmt = stmt.order_by(MarketSentiment.date.desc())
        stmt = stmt.offset(skip).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

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

    async def delete_all(self) -> int:
        result = await self.session.execute(delete(MarketSentiment))
        await self.session.flush()
        return result.rowcount
