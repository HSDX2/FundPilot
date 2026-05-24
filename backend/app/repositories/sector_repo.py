import uuid
from collections.abc import Sequence
from datetime import date, datetime
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sector import Sector, SectorMoneyFlow, SectorSnapshot
from app.repositories.base import BaseRepository


class SectorRepo(BaseRepository[Sector]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, Sector)

    async def get_by_category(self, category: str) -> Sequence[Sector]:
        stmt = select(Sector).where(Sector.category == category)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def search(
        self,
        name: str | None = None,
        category: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Sector], int]:
        query = select(Sector)
        count_query = select(func.count(Sector.id))

        conditions = []
        if name:
            conditions.append(Sector.name.ilike(f"%{name}%"))
        if category:
            conditions.append(Sector.category == category)

        if conditions:
            query = query.where(or_(*conditions))
            count_query = count_query.where(or_(*conditions))

        count_result = await self.session.execute(count_query)
        total = count_result.scalar() or 0

        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(query)
        items = list(result.scalars().all())

        return items, total

    async def get_all_active(self) -> Sequence[Sector]:
        stmt = select(Sector)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_all_names(self) -> list[tuple[uuid.UUID, str]]:
        """Return all (id, name) pairs for keyword matching."""
        stmt = select(Sector.id, Sector.name)
        result = await self.session.execute(stmt)
        return [(row.id, row.name) for row in result.all()]

    async def batch_upsert(self, records: list[dict[str, Any]]) -> tuple[int, int]:
        """Insert or update sectors by code. Returns (added, updated).

        Deduplication key: code (preferred) or name.
        """
        added = 0
        updated = 0
        seen_codes: set[str] = set()
        seen_names: set[str] = set()
        for record in records:
            code = record.get("code")
            name = record.get("name")
            if not code and not name:
                continue
            if code and code in seen_codes:
                continue
            if not code and name and name in seen_names:
                continue
            if code:
                seen_codes.add(code)
            elif name:
                seen_names.add(name)

            existing = None
            if code:
                stmt = select(Sector).where(Sector.code == code)
                result = await self.session.execute(stmt)
                existing = result.scalar_one_or_none()
            if existing is None and name:
                stmt = select(Sector).where(Sector.name == name)
                result = await self.session.execute(stmt)
                existing = result.scalar_one_or_none()
            if existing:
                for key, value in record.items():
                    if hasattr(existing, key) and value is not None:
                        setattr(existing, key, value)
                updated += 1
            else:
                self.session.add(Sector(**record))
                added += 1
                await self.session.flush()
        return added, updated


class SectorSnapshotRepo(BaseRepository[SectorSnapshot]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, SectorSnapshot)

    async def get_by_sector_and_time_range(
        self,
        sector_id: uuid.UUID,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> Sequence[SectorSnapshot]:
        stmt = select(SectorSnapshot).where(SectorSnapshot.sector_id == sector_id)
        if start:
            stmt = stmt.where(SectorSnapshot.timestamp >= start)
        if end:
            stmt = stmt.where(SectorSnapshot.timestamp <= end)
        stmt = stmt.order_by(SectorSnapshot.timestamp.desc())
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_latest_by_sector(
        self,
        sector_id: uuid.UUID,
    ) -> SectorSnapshot | None:
        stmt = (
            select(SectorSnapshot)
            .where(SectorSnapshot.sector_id == sector_id)
            .order_by(SectorSnapshot.timestamp.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_rank_by_timestamp(
        self,
        timestamp: datetime,
        category: str | None = None,
        limit: int = 20,
    ) -> Sequence[tuple[SectorSnapshot, Sector]]:
        """Get sector snapshots ranked by change_pct at a given timestamp."""
        stmt = (
            select(SectorSnapshot, Sector)
            .join(Sector, SectorSnapshot.sector_id == Sector.id)
            .where(SectorSnapshot.timestamp == timestamp)
        )
        if category:
            stmt = stmt.where(Sector.category == category)
        stmt = stmt.order_by(SectorSnapshot.change_pct.desc()).limit(limit)
        result = await self.session.execute(stmt)
        return result.all()

    async def batch_upsert_snapshots(
        self,
        records: list[dict[str, Any]],
    ) -> tuple[int, int]:
        """Bulk upsert sector snapshots. Returns (added, updated).

        Deduplication key: (sector_id, timestamp).
        """
        added = 0
        updated = 0
        seen: set[tuple[uuid.UUID, datetime]] = set()
        for record in records:
            sector_id = record.get("sector_id")
            timestamp = record.get("timestamp")
            if not sector_id or not timestamp:
                continue
            key = (sector_id, timestamp)
            if key in seen:
                continue
            seen.add(key)
            stmt = select(SectorSnapshot).where(
                SectorSnapshot.sector_id == sector_id,
                SectorSnapshot.timestamp == timestamp,
            )
            result = await self.session.execute(stmt)
            existing = result.scalar_one_or_none()
            if existing:
                for key_name, value in record.items():
                    if hasattr(existing, key_name) and value is not None:
                        setattr(existing, key_name, value)
                updated += 1
            else:
                self.session.add(SectorSnapshot(**record))
                added += 1
                await self.session.flush()
        return added, updated


class SectorMoneyFlowRepo(BaseRepository[SectorMoneyFlow]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, SectorMoneyFlow)

    async def get_by_sector_and_date(
        self,
        sector_id: uuid.UUID,
        query_date: date,
    ) -> SectorMoneyFlow | None:
        stmt = select(SectorMoneyFlow).where(
            SectorMoneyFlow.sector_id == sector_id,
            SectorMoneyFlow.date == query_date,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def batch_upsert(self, records: list[dict[str, Any]]) -> tuple[int, int]:
        """Bulk upsert sector money flow. Returns (added, updated).

        Deduplication key: (sector_id, date).
        """
        added = 0
        updated = 0
        seen: set[tuple[uuid.UUID, date]] = set()
        for record in records:
            sector_id = record.get("sector_id")
            flow_date = record.get("date")
            if not sector_id or not flow_date:
                continue
            key = (sector_id, flow_date)
            if key in seen:
                continue
            seen.add(key)
            stmt = select(SectorMoneyFlow).where(
                SectorMoneyFlow.sector_id == sector_id,
                SectorMoneyFlow.date == flow_date,
            )
            result = await self.session.execute(stmt)
            existing = result.scalar_one_or_none()
            if existing:
                for key_name, value in record.items():
                    if hasattr(existing, key_name) and value is not None:
                        setattr(existing, key_name, value)
                updated += 1
            else:
                self.session.add(SectorMoneyFlow(**record))
                added += 1
                await self.session.flush()
        return added, updated
