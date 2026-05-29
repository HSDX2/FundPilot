from datetime import datetime
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.news import NewsArticle, NewsSectorLink
from app.repositories.base import BaseRepository


class NewsArticleRepo(BaseRepository[NewsArticle]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, NewsArticle)

    async def find_by_url(self, url: str) -> NewsArticle | None:
        stmt = select(NewsArticle).where(NewsArticle.url == url)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def count_unanalyzed(self, start: datetime | None = None, end: datetime | None = None) -> int:
        """Count news articles with no sentiment score, optionally filtered by date range."""
        from sqlalchemy import select as sa_select

        stmt = sa_select(func.count(NewsArticle.id)).where(
            NewsArticle.sentiment_score.is_(None),
        )
        if start:
            stmt = stmt.where(NewsArticle.published_at >= start)
        if end:
            stmt = stmt.where(NewsArticle.published_at <= end)
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def batch_upsert(self, records: list[dict[str, Any]]) -> tuple[int, int]:
        """Insert or update news articles by URL. Returns (added, updated)."""
        added = 0
        updated = 0
        seen_urls: set[str] = set()
        for record in records:
            url = record.get("url")
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)

            existing = await self.find_by_url(url)
            if existing:
                for key, value in record.items():
                    if hasattr(existing, key) and value is not None:
                        setattr(existing, key, value)
                updated += 1
            else:
                self.session.add(NewsArticle(**record))
                added += 1
                await self.session.flush()
        return added, updated

    async def search(
        self,
        keyword: str | None = None,
        source: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        page: int = 1,
        page_size: int = 20,
        sentiment_null: bool = False,
    ) -> tuple[list[NewsArticle], int]:
        query = select(NewsArticle)
        count_query = select(func.count(NewsArticle.id))

        conditions = []
        if keyword:
            keyword_filter = or_(
                NewsArticle.title.ilike(f"%{keyword}%"),
                NewsArticle.content.ilike(f"%{keyword}%"),
            )
            conditions.append(keyword_filter)
        if source:
            conditions.append(NewsArticle.source == source)
        if start:
            conditions.append(NewsArticle.published_at >= start)
        if end:
            conditions.append(NewsArticle.published_at <= end)
        if sentiment_null:
            conditions.append(NewsArticle.sentiment_score.is_(None))

        if conditions:
            query = query.where(and_(*conditions))
            count_query = count_query.where(and_(*conditions))

        query = query.order_by(NewsArticle.published_at.desc())

        count_result = await self.session.execute(count_query)
        total = count_result.scalar() or 0

        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(query)
        items = list(result.scalars().all())

        return items, total


class NewsSectorLinkRepo(BaseRepository[NewsSectorLink]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, NewsSectorLink)

    async def batch_insert(self, links: list[dict[str, Any]]) -> int:
        """Insert news-sector links, skipping duplicates. Returns count inserted."""
        inserted = 0
        for link in links:
            self.session.add(NewsSectorLink(**link))
            inserted += 1
        await self.session.flush()
        return inserted
