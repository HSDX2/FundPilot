"""板块相关 API 路由."""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_sector_repo, get_sector_service
from app.core.database import get_db
from app.core.errors import ErrorCode, InvalidArgumentError, SectorNotFoundError
from app.core.response import ApiResponse
from app.core.task_lock import collect_lock, sector_batch_lock
from app.repositories.sector_repo import SectorRepo
from app.schemas.fund import CollectDataResponse
from app.schemas.sector import SectorDetailResponse, SectorResponse
from app.schemas.sector import SectorMoneyFlowRankListData, SectorResponse
from app.services.sector_service import SectorService

router = APIRouter(prefix="/sectors", tags=["板块"])


def _parse_uuid(sector_id: str) -> uuid.UUID:
    try:
        return uuid.UUID(sector_id)
    except ValueError:
        raise InvalidArgumentError("板块 ID 格式无效")


@router.get(
    "",
    summary="查询板块列表",
    description="分页查询板块列表，支持按分类和名称筛选",
)
async def list_sectors(
    page: int = Query(default=1, ge=1, description="页码，从 1 开始"),
    page_size: int = Query(
        default=20, ge=1, le=500, description="每页数量，最大 500"
    ),
    category: str | None = Query(
        default=None, description="板块分类：industry（行业）或 concept（概念）"
    ),
    name: str | None = Query(default=None, description="板块名称模糊搜索"),
    service: SectorService = Depends(get_sector_service),
):
    data = await service.search_sectors(
        name=name, category=category, page=page, page_size=page_size,
    )
    return ApiResponse.success(data.model_dump())


@router.get(
    "/money-flow/rank",
    summary="查询板块资金流向排行",
    description=(
        "从 THS 获取板块资金流向排行，支持当天/3日/5日/10日周期。"
        "返回所有板块按净流入降序排列。"
    ),
)
async def get_money_flow_rank(
    period: str = Query(
        default="today",
        description="周期：today（当天）/ 3d（3日）/ 5d（5日）/ 10d（10日）",
    ),
    sector_type: str | None = Query(
        default=None,
        description="板块类型：industry（行业）/ concept（概念），留空则返回全部",
    ),
    service: SectorService = Depends(get_sector_service),
):
    data = await service.get_money_flow_rank(
        period=period, sector_type=sector_type,
    )
    return ApiResponse.success(data.model_dump())


@router.get(
    "/{sector_id}",
    summary="查询板块详情",
    description="根据板块 ID 查询板块基本信息",
)
async def get_sector(
    sector_id: str = Path(description="板块 UUID"),
    repo: SectorRepo = Depends(get_sector_repo),
    service: SectorService = Depends(get_sector_service),
):
    sid = _parse_uuid(sector_id)
    sector = await repo.get(sid)
    if sector is None:
        raise SectorNotFoundError(sector_id)

    base = SectorResponse.model_validate(sector).model_dump()
    detail = SectorDetailResponse(**base)

    # 最新收盘快照（price / change_pct / volume）
    if service._snapshot_repo:
        snapshot = await service._snapshot_repo.get_latest_by_sector(sid)
        if snapshot:
            detail.price = snapshot.price
            detail.change_pct = snapshot.change_pct
            detail.volume = snapshot.volume

    # 实时估算数据
    realtime_data = await service.get_sector_realtime(sid)
    if realtime_data and "realtime" in realtime_data:
        detail.realtime = realtime_data["realtime"]

    return ApiResponse.success(detail.model_dump())


@router.get(
    "/{sector_id}/snapshots",
    summary="查询板块行情快照",
    description="查询指定板块的历史行情快照数据，支持时间范围筛选",
)
async def get_sector_snapshots(
    sector_id: str = Path(description="板块 UUID"),
    start_time: str | None = Query(
        default=None, description="开始日期，格式 YYYY-MM-DD"
    ),
    end_time: str | None = Query(
        default=None, description="结束日期，格式 YYYY-MM-DD"
    ),
    repo: SectorRepo = Depends(get_sector_repo),
    service: SectorService = Depends(get_sector_service),
):
    sid = _parse_uuid(sector_id)
    sector = await repo.get(sid)
    if sector is None:
        raise SectorNotFoundError(sector_id)

    start = date.fromisoformat(start_time) if start_time else None
    end = date.fromisoformat(end_time) if end_time else None

    data = await service.get_sector_snapshots(sid, start, end)
    return ApiResponse.success(data.model_dump())


@router.get(
    "/{sector_id}/realtime",
    summary="查询板块实时行情",
    description="查询指定板块的最新实时行情快照",
)
async def get_sector_realtime(
    sector_id: str = Path(description="板块 UUID"),
    repo: SectorRepo = Depends(get_sector_repo),
    service: SectorService = Depends(get_sector_service),
):
    sid = _parse_uuid(sector_id)
    sector = await repo.get(sid)
    if sector is None:
        raise SectorNotFoundError(sector_id)

    snapshot = await service.get_sector_realtime(sid)
    if snapshot is None:
        return ApiResponse.success(data=None)
    return ApiResponse.success(snapshot)


@router.get(
    "/rank/current",
    summary="查询板块涨跌排行",
    description="按涨跌幅排序的当前板块排行，支持按分类筛选",
)
async def get_sector_rank(
    category: str | None = Query(
        default=None, description="板块分类筛选：industry（行业）或 concept（概念）"
    ),
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=30, ge=1, le=200, description="每页条数"),
    sort_by: str = Query(
        default="realtime_change_pct",
        description="排序字段：change_pct（最新收盘涨跌幅）/ realtime_change_pct（实时涨跌幅，默认）",
    ),
    watched_only: bool = Query(
        default=False, description="是否只显示已关注的板块",
    ),
    session: AsyncSession = Depends(get_db),
    service: SectorService = Depends(get_sector_service),
):
    watched_ids = None
    if watched_only:
        from app.models.watchlist import WatchedSector
        from sqlalchemy import select
        result = await session.execute(select(WatchedSector.sector_id))
        watched_ids = {row.sector_id for row in result}

    all_data = await service.get_rank(
        session, category=category, limit=500, sort_by=sort_by,
        watched_ids=watched_ids,
    )
    # 服务端分页
    start = (page - 1) * page_size
    page_items = all_data.items[start:start + page_size]
    from app.schemas.sector import SectorRankListData
    return ApiResponse.success(
        SectorRankListData(
            items=page_items, total=len(all_data.items),
            page=page, page_size=page_size,
        ).model_dump()
    )


@router.get(
    "/{sector_id}/money-flow",
    summary="查询板块资金流向",
    description="查询指定板块的历史资金流向数据，支持日期范围筛选",
)
async def get_sector_money_flow(
    sector_id: str = Path(description="板块 UUID"),
    start_date: str | None = Query(
        default=None, description="开始日期，格式 YYYY-MM-DD",
    ),
    end_date: str | None = Query(
        default=None, description="结束日期，格式 YYYY-MM-DD",
    ),
    repo: SectorRepo = Depends(get_sector_repo),
):
    from datetime import date


    sid = _parse_uuid(sector_id)
    sector = await repo.get(sid)
    if sector is None:
        raise SectorNotFoundError(sector_id)

    # Access money flow data via sector relationship
    flows = list(sector.money_flows) if sector.money_flows else []
    if start_date:
        sd = date.fromisoformat(start_date)
        flows = [f for f in flows if f.date >= sd]
    if end_date:
        ed = date.fromisoformat(end_date)
        flows = [f for f in flows if f.date <= ed]

    from app.schemas.sector import SectorMoneyFlowResponse
    items = [SectorMoneyFlowResponse.model_validate(f) for f in flows]
    return ApiResponse.success({"items": [item.model_dump() for item in items]})


@router.post(
    "/{sector_id}/collect-data",
    summary="采集板块历史数据",
    description="从数据源采集板块的历史资金流向、行情快照和涨跌幅数据，直接覆盖已有数据",
)
async def collect_sector_data(
    sector_id: str = Path(description="板块 UUID"),
    mode: str = Query(default="all", description="all=获取全部历史数据, incremental=增量获取最新数据"),
    start_date: str | None = Query(default=None, description="数据起始日期，格式 YYYY-MM-DD。留空 = 全部历史"),
    backfill_mf_detail: bool = Query(
        default=True,
        description=(
            "是否补充中单/散户资金流向细分数据。"
            "EM push2his 接口可能被 WAF 拦截导致获取失败，"
            "关闭后仅通过 THS 获取资金总额（无中单/散户细分）。"
        ),
    ),
    service: SectorService = Depends(get_sector_service),
):
    sid = _parse_uuid(sector_id)

    # 检查全局批量任务锁（批量历史/每日任务正在执行）
    if sector_batch_lock.status["running"]:
        return ApiResponse.error(
            code=ErrorCode.TASK_RUNNING,
            message="板块批量采集任务正在执行中，请稍后重试",
        )

    lock_key = f"sector:{sid}:{mode}"
    if not await collect_lock.try_acquire(lock_key, f"collect-sector-data-{sid}-{mode}"):
        return ApiResponse.error(
            code=ErrorCode.TASK_RUNNING,
            message=f"板块 {sector_id} 的采集任务正在执行中，请稍后重试",
        )
    try:
        if mode == "all":
            result = await service.collect_data_all(sid, start_date=start_date)
        else:
            result = await service.collect_data_incremental(sid, backfill_mf_detail=backfill_mf_detail)
    finally:
        collect_lock.release(lock_key)
    return ApiResponse.success(CollectDataResponse(**result).model_dump())
