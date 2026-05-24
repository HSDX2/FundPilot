"""Sector business logic — data transformation and orchestration."""

import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sector import SectorSnapshot
from app.repositories.sector_repo import (
    SectorMoneyFlowRepo,
    SectorRepo,
    SectorSnapshotRepo,
)
from app.schemas.sector import (
    SectorListData,
    SectorRankItem,
    SectorRankListData,
    SectorResponse,
    SectorSnapshotListData,
    SectorSnapshotResponse,
)


class SectorService:
    """Sector-related business logic."""

    def __init__(
        self,
        sector_repo: SectorRepo,
        sector_snapshot_repo: SectorSnapshotRepo | None = None,
        sector_money_flow_repo: SectorMoneyFlowRepo | None = None,
    ):
        self._sector_repo = sector_repo
        self._snapshot_repo = sector_snapshot_repo
        self._money_flow_repo = sector_money_flow_repo

    async def search_sectors(
        self,
        name: str | None = None,
        category: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> SectorListData:
        items, total = await self._sector_repo.search(
            name=name,
            category=category,
            page=page,
            page_size=page_size,
        )
        return SectorListData(
            items=[SectorResponse.model_validate(s) for s in items],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def get_sector_by_id(self, sector_id: uuid.UUID) -> SectorResponse | None:
        sector = await self._sector_repo.get(sector_id)
        if sector is None:
            return None
        return SectorResponse.model_validate(sector)

    async def get_sector_snapshots(
        self,
        sector_id: uuid.UUID,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> SectorSnapshotListData:
        if self._snapshot_repo is None:
            return SectorSnapshotListData(items=[])
        snapshots = await self._snapshot_repo.get_by_sector_and_time_range(
            sector_id, start_time, end_time,
        )
        return SectorSnapshotListData(
            items=[SectorSnapshotResponse.model_validate(s) for s in snapshots],
        )

    async def get_sector_realtime(
        self,
        sector_id: uuid.UUID,
    ) -> SectorSnapshotResponse | None:
        if self._snapshot_repo is None:
            return None
        snapshot = await self._snapshot_repo.get_latest_by_sector(sector_id)
        if snapshot is None:
            return None
        return SectorSnapshotResponse.model_validate(snapshot)

    async def get_rank(
        self,
        session: AsyncSession,
        category: str | None = None,
        limit: int = 20,
    ) -> SectorRankListData:
        if self._snapshot_repo is None:
            return SectorRankListData(items=[])

        ts_stmt = select(func.max(SectorSnapshot.timestamp))
        ts_result = await session.execute(ts_stmt)
        latest_ts = ts_result.scalar()
        if latest_ts is None:
            return SectorRankListData(items=[])

        rows = await self._snapshot_repo.get_rank_by_timestamp(
            latest_ts, category=category, limit=limit,
        )

        items = []
        for snapshot, sector in rows:
            items.append(
                SectorRankItem(
                    sector_id=sector.id,
                    sector_name=sector.name,
                    category=sector.category,
                    price=snapshot.price,
                    change_pct=snapshot.change_pct,
                    timestamp=snapshot.timestamp,
                )
            )
        return SectorRankListData(items=items)
