import uuid
from collections.abc import Sequence
from datetime import date
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

    async def get_by_codes(self, codes: list[str]) -> list[Fund]:
        """Batch query funds by code list."""
        stmt = select(Fund).where(Fund.code.in_(codes))
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def search(
        self,
        name: str | None = None,
        type_: str | None = None,
        company: str | None = None,
        page: int = 1,
        page_size: int = 20,
        sort_by: str | None = None,
        sort_order: str = "desc",
        watched_only: bool = False,
    ) -> tuple[list[Fund], int]:
        from app.models.watchlist import WatchedFund

        query = select(Fund)
        count_query = select(func.count(Fund.id))

        conditions = []
        if name:
            conditions.append(Fund.name.ilike(f"%{name}%"))
        if type_:
            conditions.append(Fund.type.like(f"{type_}%"))
        if company:
            conditions.append(Fund.company.ilike(f"%{company}%"))
        if watched_only:
            subq = select(WatchedFund.fund_id).select_from(WatchedFund)
            conditions.append(Fund.id.in_(subq))

        if conditions:
            query = query.where(or_(*conditions))
            count_query = count_query.where(or_(*conditions))

        # Total count
        count_result = await self.session.execute(count_query)
        total = count_result.scalar() or 0

        # Sorting
        from app.models.fund import FundEstimate
        from sqlalchemy.orm import noload
        sort_col = None
        if sort_by and sort_by == "estimate_change_pct":
            # JOIN fund_estimates 按实时涨跌幅排序，null 回退到 latest_change_pct
            query = query.options(noload(Fund.navs), noload(Fund.estimates))
            query = query.outerjoin(
                FundEstimate, FundEstimate.fund_id == Fund.id,
            )
            est_col = FundEstimate.estimate_change_pct
            fallback_col = Fund.latest_change_pct
            if sort_order == "desc":
                sort_col = func.coalesce(est_col, fallback_col).desc().nullslast()
            else:
                sort_col = func.coalesce(est_col, fallback_col).asc().nullslast()
        elif sort_by and hasattr(Fund, sort_by):
            col = getattr(Fund, sort_by)
            sort_col = col.desc() if sort_order == "desc" else col.asc()
            sort_col = sort_col.nullslast()

        if sort_col is not None:
            query = query.order_by(sort_col)
        else:
            query = query.order_by(Fund.latest_change_pct.desc().nullslast())

        # Paginated query
        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(query)
        items = list(result.scalars().all())

        return items, total

    async def get_all(self) -> list[Fund]:
        """Fetch all funds without pagination."""
        stmt = select(Fund)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_code_id_map(self) -> dict[str, uuid.UUID]:
        """Return {code: id} for all funds — 只查两列，不加载关联表."""
        stmt = select(Fund.code, Fund.id)
        result = await self.session.execute(stmt)
        return {row.code: row.id for row in result}

    async def get_all_lean(self) -> list[Fund]:
        """Fetch all funds without relationship loading."""
        from sqlalchemy.orm import noload

        stmt = select(Fund).options(noload(Fund.navs), noload(Fund.estimates))
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def find_missing_basic_info(self, limit: int = 100) -> list[Fund]:
        """Return funds where company is NULL (basic info not yet fetched)."""
        stmt = (
            select(Fund)
            .where(Fund.company.is_(None))
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

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

    async def get_latest_nav_by_fund(self, fund_id: uuid.UUID) -> FundNav | None:
        """Get the most recent NAV record for a fund."""
        stmt = (
            select(FundNav)
            .where(FundNav.fund_id == fund_id)
            .order_by(FundNav.date.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_latest_nav_dates(
        self, fund_ids: list[uuid.UUID],
    ) -> dict[uuid.UUID, date]:
        """Bulk query the latest NAV date per fund. Skips funds with no NAV."""
        stmt = (
            select(FundNav.fund_id, func.max(FundNav.date).label("max_date"))
            .where(FundNav.fund_id.in_(fund_ids))
            .group_by(FundNav.fund_id)
        )
        result = await self.session.execute(stmt)
        return {row.fund_id: row.max_date for row in result}

    async def get_latest_navs(
        self, fund_ids: list[uuid.UUID],
    ) -> dict[uuid.UUID, FundNav]:
        """Bulk query the full latest NAV record per fund using DISTINCT ON."""
        if not fund_ids:
            return {}
        stmt = (
            select(FundNav)
            .where(FundNav.fund_id.in_(fund_ids))
            .distinct(FundNav.fund_id)
            .order_by(FundNav.fund_id, FundNav.date.desc())
        )
        result = await self.session.execute(stmt)
        return {row.fund_id: row for row in result.scalars().all()}


class FundEstimateRepo(BaseRepository[FundEstimate]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, FundEstimate)

    async def get_by_fund(self, fund_id: uuid.UUID) -> FundEstimate | None:
        stmt = select(FundEstimate).where(FundEstimate.fund_id == fund_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def upsert(
        self, fund_id: uuid.UUID, *, estimate_nav: float | None = None,
        estimate_change_pct: float | None = None,
    ) -> FundEstimate:
        """Insert or update the single estimate row for a fund."""
        existing = await self.get_by_fund(fund_id)
        if existing:
            if estimate_nav is not None:
                existing.estimate_nav = estimate_nav
            if estimate_change_pct is not None:
                existing.estimate_change_pct = estimate_change_pct
            return existing
        obj = FundEstimate(
            fund_id=fund_id, estimate_nav=estimate_nav,
            estimate_change_pct=estimate_change_pct,
        )
        self.session.add(obj)
        await self.session.flush()
        return obj

    async def batch_upsert(
        self, records: list[dict],
    ) -> tuple[int, int]:
        """批量写入或更新基金实时估值。分批避免超 PostgreSQL 参数上限（32767）。

        返回 (added, updated)。由于 uq_fund_estimate_fund 约束保证 fund_id 唯一，
        首次运行全部为新增，后续运行全部为更新。
        """
        if not records:
            return 0, 0

        from sqlalchemy.dialects.postgresql import insert as pg_insert

        # 去重（fund_id 唯一）
        seen: set[uuid.UUID] = set()
        deduped = []
        for r in records:
            fid = r.get("fund_id")
            if not fid or fid in seen:
                continue
            seen.add(fid)
            deduped.append(r)

        # 检查已存在的 fund_id，用于区分新增和更新
        stmt = select(FundEstimate.fund_id).where(FundEstimate.fund_id.in_(seen))
        existing = set()
        for row in await self.session.execute(stmt):
            existing.add(row.fund_id)

        added = 0
        updated = 0
        batch_size = 5000
        for i in range(0, len(deduped), batch_size):
            batch = deduped[i:i + batch_size]
            stmt = pg_insert(FundEstimate).values(batch)
            stmt = stmt.on_conflict_do_update(
                constraint="uq_fund_estimate_fund",
                set_={
                    "estimate_nav": stmt.excluded.estimate_nav,
                    "estimate_change_pct": stmt.excluded.estimate_change_pct,
                    "updated_at": func.now(),
                },
            )
            await self.session.execute(stmt)
            for rec in batch:
                fid = rec.get("fund_id")
                if fid in existing:
                    updated += 1
                else:
                    added += 1
        return added, updated
