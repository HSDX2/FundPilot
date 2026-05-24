"""板块相关 API 路由."""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_sector_repo, get_sector_service
from app.core.database import get_db
from app.core.errors import InvalidArgumentError, SectorNotFoundError
from app.core.response import ApiResponse
from app.repositories.sector_repo import SectorRepo
from app.schemas.sector import SectorResponse
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
        default=20, ge=1, le=100, description="每页数量，最大 100"
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
    "/{sector_id}",
    summary="查询板块详情",
    description="根据板块 ID 查询板块基本信息",
)
async def get_sector(
    sector_id: str = Path(description="板块 UUID"),
    repo: SectorRepo = Depends(get_sector_repo),
):
    sid = _parse_uuid(sector_id)
    sector = await repo.get(sid)
    if sector is None:
        raise SectorNotFoundError(sector_id)
    return ApiResponse.success(
        SectorResponse.model_validate(sector).model_dump()
    )


@router.get(
    "/{sector_id}/snapshots",
    summary="查询板块行情快照",
    description="查询指定板块的历史行情快照数据，支持时间范围筛选",
)
async def get_sector_snapshots(
    sector_id: str = Path(description="板块 UUID"),
    start_time: str | None = Query(
        default=None, description="开始时间，ISO 格式，如 2026-05-23T09:30:00"
    ),
    end_time: str | None = Query(
        default=None, description="结束时间，ISO 格式，如 2026-05-23T15:00:00"
    ),
    repo: SectorRepo = Depends(get_sector_repo),
    service: SectorService = Depends(get_sector_service),
):
    sid = _parse_uuid(sector_id)
    sector = await repo.get(sid)
    if sector is None:
        raise SectorNotFoundError(sector_id)

    start = datetime.fromisoformat(start_time) if start_time else None
    end = datetime.fromisoformat(end_time) if end_time else None

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
    return ApiResponse.success(snapshot.model_dump())


@router.get(
    "/rank/current",
    summary="查询板块涨跌排行",
    description="按涨跌幅排序的当前板块排行，支持按分类筛选",
)
async def get_sector_rank(
    category: str | None = Query(
        default=None, description="板块分类筛选：industry（行业）或 concept（概念）"
    ),
    limit: int = Query(
        default=20, ge=1, le=100, description="返回条数，最大 100"
    ),
    session: AsyncSession = Depends(get_db),
    service: SectorService = Depends(get_sector_service),
):
    data = await service.get_rank(session, category=category, limit=limit)
    return ApiResponse.success(data.model_dump())


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
