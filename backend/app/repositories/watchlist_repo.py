"""关注列表仓库."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.fund import Fund
from app.models.sector import Sector
from app.models.watchlist import WatchedFund, WatchedSector


class WatchedFundRepo:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def is_watched(self, fund_id: uuid.UUID) -> bool:
        stmt = select(WatchedFund).where(WatchedFund.fund_id == fund_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def add(self, fund_id: uuid.UUID) -> WatchedFund:
        wf = WatchedFund(fund_id=fund_id)
        self.session.add(wf)
        await self.session.flush()
        return wf

    async def get_by_fund_id(self, fund_id: uuid.UUID) -> WatchedFund | None:
        stmt = select(WatchedFund).where(WatchedFund.fund_id == fund_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def remove(self, fund_id: uuid.UUID) -> bool:
        stmt = select(WatchedFund).where(WatchedFund.fund_id == fund_id)
        result = await self.session.execute(stmt)
        wf = result.scalar_one_or_none()
        if wf is None:
            return False
        await self.session.delete(wf)
        await self.session.flush()
        return True

    async def list_all(self) -> list[WatchedFund]:
        stmt = (
            select(WatchedFund)
            .order_by(WatchedFund.added_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count(self) -> int:
        from sqlalchemy import func
        stmt = select(func.count()).select_from(WatchedFund)
        result = await self.session.execute(stmt)
        return result.scalar() or 0


class WatchedSectorRepo:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def is_watched(self, sector_id: uuid.UUID) -> bool:
        stmt = select(WatchedSector).where(WatchedSector.sector_id == sector_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def add(self, sector_id: uuid.UUID) -> WatchedSector:
        ws = WatchedSector(sector_id=sector_id)
        self.session.add(ws)
        await self.session.flush()
        return ws

    async def remove(self, sector_id: uuid.UUID) -> bool:
        stmt = select(WatchedSector).where(WatchedSector.sector_id == sector_id)
        result = await self.session.execute(stmt)
        ws = result.scalar_one_or_none()
        if ws is None:
            return False
        await self.session.delete(ws)
        await self.session.flush()
        return True

    async def list_all(self) -> list[WatchedSector]:
        stmt = (
            select(WatchedSector)
            .order_by(WatchedSector.added_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count(self) -> int:
        from sqlalchemy import func
        stmt = select(func.count()).select_from(WatchedSector)
        result = await self.session.execute(stmt)
        return result.scalar() or 0
