import uuid
from collections.abc import Sequence
from datetime import date
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sector import Sector, SectorMoneyFlow, SectorRealtime, SectorSnapshot
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
            query = query.where(and_(*conditions))
            count_query = count_query.where(and_(*conditions))

        count_result = await self.session.execute(count_query)
        total = count_result.scalar() or 0

        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(query)
        items = list(result.scalars().all())

        return items, total

    async def get_all_active(self) -> Sequence[Sector]:
        from sqlalchemy.orm import noload

        stmt = select(Sector).options(
            noload(Sector.snapshots),
            noload(Sector.money_flows),
            noload(Sector.realtime),
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_active_by_category(self, category: str) -> Sequence[Sector]:
        from sqlalchemy.orm import noload

        stmt = select(Sector).where(Sector.category == category).options(
            noload(Sector.snapshots),
            noload(Sector.money_flows),
            noload(Sector.realtime),
        )
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
        start: date | None = None,
        end: date | None = None,
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

    async def get_latest_before_date(
        self,
        sector_id: uuid.UUID,
        before_date: date,
    ) -> SectorSnapshot | None:
        """获取指定日期之前的最近一条快照（用于计算涨跌幅基准）。"""
        stmt = (
            select(SectorSnapshot)
            .where(
                SectorSnapshot.sector_id == sector_id,
                SectorSnapshot.timestamp < before_date,
            )
            .order_by(SectorSnapshot.timestamp.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_latest_per_sector(
        self,
        sector_ids: Sequence[uuid.UUID],
    ) -> Sequence[SectorSnapshot]:
        """Get the latest snapshot for each sector using DISTINCT ON.

        Uses PostgreSQL ``DISTINCT ON (sector_id)`` with ``ORDER BY
        sector_id, timestamp DESC`` for a single index scan — much faster
        than the subquery + JOIN approach on large tables.
        """
        stmt = (
            select(SectorSnapshot)
            .where(SectorSnapshot.sector_id.in_(sector_ids))
            .distinct(SectorSnapshot.sector_id)
            .order_by(SectorSnapshot.sector_id, SectorSnapshot.timestamp.desc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_rank_by_timestamp(
        self,
        timestamp: date,
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
        seen: set[tuple[uuid.UUID, date]] = set()
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

    async def get_latest_complete_date(
        self,
        sector_id: uuid.UUID,
    ) -> date | None:
        """获取中单/散户资金流向数据有值的最新日期（用于增量回补起始点）。"""
        stmt = select(SectorMoneyFlow.date).where(
            SectorMoneyFlow.sector_id == sector_id,
            SectorMoneyFlow.retail_net_inflow.isnot(None),
            SectorMoneyFlow.middle_net_inflow.isnot(None),
        ).order_by(SectorMoneyFlow.date.desc()).limit(1)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all_date_ranges(
        self,
    ) -> dict[uuid.UUID, tuple[date, date]]:
        """返回所有板块资金流数据的最早和最晚日期。

        一次 SQL 查询，结果按 sector_id 索引。
        """
        stmt = select(
            SectorMoneyFlow.sector_id,
            func.min(SectorMoneyFlow.date),
            func.max(SectorMoneyFlow.date),
        ).group_by(SectorMoneyFlow.sector_id)
        result = await self.session.execute(stmt)
        return {
            row[0]: (row[1], row[2])
            for row in result.all()
        }

    async def batch_upsert(
        self, records: list[dict[str, Any]],
    ) -> tuple[int, int]:
        """批量写入或更新板块资金流向。返回 (新增数, 更新数)。

        Deduplication key: (sector_id, date).
        已有数据会被直接覆盖。
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


class SectorRealtimeRepo(BaseRepository[SectorRealtime]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, SectorRealtime)

    async def get_by_sector(self, sector_id: uuid.UUID) -> SectorRealtime | None:
        stmt = select(SectorRealtime).where(SectorRealtime.sector_id == sector_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_sectors(
        self, sector_ids: list[uuid.UUID],
    ) -> dict[uuid.UUID, SectorRealtime]:
        """批量查询多个板块的实时行情，返回 {sector_id: record} 字典。"""
        if not sector_ids:
            return {}
        stmt = select(SectorRealtime).where(
            SectorRealtime.sector_id.in_(sector_ids),
        )
        result = await self.session.execute(stmt)
        return {r.sector_id: r for r in result.scalars().all()}

    async def batch_upsert(self, records: list[dict]) -> tuple[int, int]:
        """批量写入或更新板块实时行情。返回 (新增数, 更新数)。"""
        added = 0
        updated = 0
        seen: set[uuid.UUID] = set()
        for record in records:
            sector_id = record.get("sector_id")
            if not sector_id or sector_id in seen:
                continue
            seen.add(sector_id)
            existing = await self.get_by_sector(sector_id)
            if existing:
                for key, value in record.items():
                    if hasattr(existing, key) and value is not None:
                        setattr(existing, key, value)
                updated += 1
            else:
                self.session.add(SectorRealtime(**record))
                added += 1
                await self.session.flush()
        return added, updated
