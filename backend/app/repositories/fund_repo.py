import uuid
from collections.abc import Sequence
from datetime import date, datetime
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.fund import Fund, FundEstimate, FundNav
from app.repositories.base import BaseRepository


class FundRepo(BaseRepository[Fund]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, Fund)

    async def get_by_code(self, code: str) -> Fund | None:
        stmt = select(Fund).where(Fund.code == code)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def search(
        self,
        name: str | None = None,
        type_: str | None = None,
        company: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Fund], int]:
        query = select(Fund)
        count_query = select(func.count(Fund.id))

        conditions = []
        if name:
            conditions.append(Fund.name.ilike(f"%{name}%"))
        if type_:
            conditions.append(Fund.type.like(f"{type_}%"))
        if company:
            conditions.append(Fund.company.ilike(f"%{company}%"))

        if conditions:
            query = query.where(or_(*conditions))
            count_query = count_query.where(or_(*conditions))

        # Total count
        count_result = await self.session.execute(count_query)
        total = count_result.scalar() or 0

        # Paginated query
        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(query)
        items = list(result.scalars().all())

        return items, total

    async def batch_upsert(self, records: list[dict[str, Any]]) -> tuple[int, int]:
        """Insert or update funds in batch. Returns (added, updated) counts.

        Deduplication is guaranteed by fund code: records with the same code
        are merged, and already-persisted codes are updated in-place.
        """
        added = 0
        updated = 0
        seen: set[str] = set()
        for record in records:
            code = record.get("code")
            if not code or code in seen:
                continue
            seen.add(code)
            existing = await self.get_by_code(code)
            if existing:
                for key, value in record.items():
                    if hasattr(existing, key) and value is not None:
                        setattr(existing, key, value)
                updated += 1
            else:
                obj = Fund(**record)
                self.session.add(obj)
                added += 1
                await self.session.flush()
        return added, updated


class FundNavRepo(BaseRepository[FundNav]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, FundNav)

    async def get_by_fund_and_date(
        self,
        fund_id: uuid.UUID,
        nav_date: date,
    ) -> FundNav | None:
        """Get NAV record for a fund on a specific date."""
        stmt = select(FundNav).where(
            FundNav.fund_id == fund_id,
            FundNav.date == nav_date,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def batch_upsert_nav(
        self,
        records: list[dict[str, Any]],
    ) -> tuple[int, int]:
        """Bulk upsert fund NAV records. Returns (added, updated).

        Deduplication key: (fund_id, date).
        """
        added = 0
        updated = 0
        seen: set[tuple[uuid.UUID, date]] = set()
        for record in records:
            fund_id = record.get("fund_id")
            nav_date = record.get("date")
            if not fund_id or not nav_date:
                continue
            key = (fund_id, nav_date)
            if key in seen:
                continue
            seen.add(key)
            stmt = select(FundNav).where(
                FundNav.fund_id == fund_id,
                FundNav.date == nav_date,
            )
            result = await self.session.execute(stmt)
            existing = result.scalar_one_or_none()
            if existing:
                for key_name, value in record.items():
                    if hasattr(existing, key_name) and value is not None:
                        setattr(existing, key_name, value)
                updated += 1
            else:
                self.session.add(FundNav(**record))
                added += 1
                await self.session.flush()
        return added, updated

    async def get_by_fund_and_date_range(
        self,
        fund_id: uuid.UUID,
        start: date | None = None,
        end: date | None = None,
    ) -> Sequence[FundNav]:
        stmt = select(FundNav).where(FundNav.fund_id == fund_id)
        if start:
            stmt = stmt.where(FundNav.date >= start)
        if end:
            stmt = stmt.where(FundNav.date <= end)
        stmt = stmt.order_by(FundNav.date.desc())
        result = await self.session.execute(stmt)
        return result.scalars().all()


class FundEstimateRepo(BaseRepository[FundEstimate]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, FundEstimate)

    async def get_latest_by_fund(self, fund_id: uuid.UUID) -> FundEstimate | None:
        stmt = (
            select(FundEstimate)
            .where(FundEstimate.fund_id == fund_id)
            .order_by(FundEstimate.timestamp.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def batch_upsert_estimates(
        self,
        records: list[dict[str, Any]],
    ) -> tuple[int, int]:
        """Bulk upsert fund estimates. Returns (added, updated).

        Deduplication key: (fund_id, timestamp).
        """
        added = 0
        updated = 0
        seen: set[tuple[uuid.UUID, datetime]] = set()
        for record in records:
            fund_id = record.get("fund_id")
            timestamp = record.get("timestamp")
            if not fund_id or not timestamp:
                continue
            key = (fund_id, timestamp)
            if key in seen:
                continue
            seen.add(key)
            stmt = select(FundEstimate).where(
                FundEstimate.fund_id == fund_id,
                FundEstimate.timestamp == timestamp,
            )
            result = await self.session.execute(stmt)
            existing = result.scalar_one_or_none()
            if existing:
                for key_name, value in record.items():
                    if hasattr(existing, key_name) and value is not None:
                        setattr(existing, key_name, value)
                updated += 1
            else:
                self.session.add(FundEstimate(**record))
                added += 1
                await self.session.flush()
        return added, updated
