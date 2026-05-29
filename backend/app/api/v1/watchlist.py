"""关注列表 API 路由."""

import uuid

from fastapi import APIRouter, Depends, Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.errors import InvalidArgumentError
from app.core.response import ApiResponse
from app.repositories.fund_repo import FundRepo
from app.repositories.sector_repo import SectorRepo
from app.repositories.watchlist_repo import WatchedFundRepo, WatchedSectorRepo
from app.schemas.watchlist import (
    UpdateWatchedFundRequest,
    WatchedFundResponse,
    WatchedSectorResponse,
)

router = APIRouter(prefix="/watchlist", tags=["关注列表"])


def _parse_uuid(id_str: str) -> uuid.UUID:
    try:
        return uuid.UUID(id_str)
    except ValueError:
        raise InvalidArgumentError("ID 格式无效") from None


# ── 关注基金 ──────────────────────────────────────────────────────────


@router.get("/funds", summary="查询关注基金列表")
async def list_watched_funds(session: AsyncSession = Depends(get_db)):
    repo = WatchedFundRepo(session)
    fund_repo = FundRepo(session)
    from app.models.fund import FundEstimate
    from sqlalchemy import select as sa_select

    items = await repo.list_all()
    fund_ids = [wf.fund_id for wf in items]

    # 批量查询估值
    if fund_ids:
        est_result = await session.execute(
            sa_select(FundEstimate).where(FundEstimate.fund_id.in_(fund_ids)),
        )
        estimates = {e.fund_id: e for e in est_result.scalars().all()}
    else:
        estimates = {}

    result = []
    for wf in items:
        fund = await fund_repo.get(wf.fund_id)
        est = estimates.get(wf.fund_id)

        result.append({
            "id": wf.id,
            "fund_id": wf.fund_id,
            "fund_code": fund.code if fund else "",
            "fund_name": fund.name if fund else "",
            "fund_type": fund.type if fund else None,
            "estimate_nav": float(est.estimate_nav) if est and est.estimate_nav is not None else None,
            "estimate_change_pct": float(est.estimate_change_pct) if est and est.estimate_change_pct is not None else None,
            "holding_amount": wf.holding_amount,
            "added_at": wf.added_at,
        })
    return ApiResponse.success({"items": result, "total": len(result)})


@router.post("/funds/{fund_id}", summary="关注基金")
async def watch_fund(
    fund_id: str = Path(description="基金 UUID"),
    session: AsyncSession = Depends(get_db),
):
    fid = _parse_uuid(fund_id)
    fund_repo = FundRepo(session)
    fund = await fund_repo.get(fid)
    if fund is None:
        return ApiResponse.error("FUND_NOT_FOUND", "基金不存在", status_code=404)

    repo = WatchedFundRepo(session)
    if await repo.is_watched(fid):
        return ApiResponse.success(None, message="已关注，无需重复添加")

    await repo.add(fid)
    await session.commit()
    return ApiResponse.success(None, message="已关注")


@router.delete("/funds/{fund_id}", summary="取消关注基金")
async def unwatch_fund(
    fund_id: str = Path(description="基金 UUID"),
    session: AsyncSession = Depends(get_db),
):
    fid = _parse_uuid(fund_id)
    repo = WatchedFundRepo(session)
    deleted = await repo.remove(fid)
    if not deleted:
        return ApiResponse.error("NOT_WATCHED", "未关注该基金", status_code=404)
    await session.commit()
    return ApiResponse.success(None, message="已取消关注")


@router.put("/funds/{fund_id}", summary="更新关注基金信息（持仓金额）")
async def update_watched_fund(
    fund_id: str = Path(description="基金 UUID"),
    body: UpdateWatchedFundRequest = None,
    session: AsyncSession = Depends(get_db),
):
    fid = _parse_uuid(fund_id)
    repo = WatchedFundRepo(session)
    wf = await repo.get_by_fund_id(fid)
    if wf is None:
        return ApiResponse.error("NOT_WATCHED", "未关注该基金", status_code=404)
    wf.holding_amount = body.holding_amount
    await session.commit()
    return ApiResponse.success(
        {"holding_amount": wf.holding_amount},
        message="已更新",
    )


# ── 关注板块 ──────────────────────────────────────────────────────────


@router.get("/sectors", summary="查询关注板块列表")
async def list_watched_sectors(session: AsyncSession = Depends(get_db)):
    repo = WatchedSectorRepo(session)
    sector_repo = SectorRepo(session)
    from app.repositories.sector_repo import SectorSnapshotRepo, SectorRealtimeRepo
    snapshot_repo = SectorSnapshotRepo(session)
    realtime_repo = SectorRealtimeRepo(session)

    items = await repo.list_all()
    sector_ids = [ws.sector_id for ws in items]

    snapshots = await snapshot_repo.get_latest_per_sector(sector_ids)
    snap_map = {s.sector_id: s for s in snapshots}

    rt_records = await realtime_repo.get_by_sectors(sector_ids)
    rt_map = {sid: r for sid, r in rt_records.items()}

    result = []
    for ws in items:
        sector = await sector_repo.get(ws.sector_id)
        snap = snap_map.get(ws.sector_id)
        rt = rt_map.get(ws.sector_id)

        price = None
        change_pct = None
        if rt:
            price = rt.price
            change_pct = rt.change_pct
        elif snap:
            price = snap.price
            change_pct = snap.change_pct

        result.append({
            "id": ws.id,
            "sector_id": ws.sector_id,
            "sector_name": sector.name if sector else "",
            "sector_category": sector.category if sector else "",
            "price": price,
            "change_pct": change_pct,
            "added_at": ws.added_at,
        })
    return ApiResponse.success({"items": result, "total": len(result)})


@router.post("/sectors/{sector_id}", summary="关注板块")
async def watch_sector(
    sector_id: str = Path(description="板块 UUID"),
    session: AsyncSession = Depends(get_db),
):
    sid = _parse_uuid(sector_id)
    sector_repo = SectorRepo(session)
    s = await sector_repo.get(sid)
    if s is None:
        return ApiResponse.error("SECTOR_NOT_FOUND", "板块不存在", status_code=404)

    repo = WatchedSectorRepo(session)
    if await repo.is_watched(sid):
        return ApiResponse.success(None, message="已关注，无需重复添加")

    await repo.add(sid)
    await session.commit()
    return ApiResponse.success(None, message="已关注")


@router.delete("/sectors/{sector_id}", summary="取消关注板块")
async def unwatch_sector(
    sector_id: str = Path(description="板块 UUID"),
    session: AsyncSession = Depends(get_db),
):
    sid = _parse_uuid(sector_id)
    repo = WatchedSectorRepo(session)
    deleted = await repo.remove(sid)
    if not deleted:
        return ApiResponse.error("NOT_WATCHED", "未关注该板块", status_code=404)
    await session.commit()
    return ApiResponse.success(None, message="已取消关注")
