"""实时数据 API —— 直接调用 AkShare，不经过数据库."""

from fastapi import APIRouter, Path, Query

from app.core.errors import AppError, ErrorCode
from app.core.response import ApiResponse
from app.integrations.akshare.fund_datasource import FundDataSource
from app.integrations.akshare.sector_datasource import SectorDataSource

router = APIRouter(prefix="/realtime", tags=["实时数据"])


@router.get(
    "/funds/{code}",
    summary="实时查询基金估值",
    description="直接调用 AkShare 查询单只基金的实时盘中估值，不依赖数据库",
)
async def realtime_fund_estimate(
    code: str = Path(description="基金代码，如 000001"),
):
    ds = FundDataSource()
    result = await ds.fetch_estimate_by_code(code)
    if result is None:
        raise AppError(
            code=ErrorCode.DATA_SOURCE_ERROR,
            message=f"未能获取基金 {code} 的实时估值数据",
        )
    return ApiResponse.success(result)


@router.get(
    "/funds/{code}/nav",
    summary="实时查询基金净值历史",
    description="直接调用 AkShare 查询单只基金的历史净值（单位净值走势），不依赖数据库",
)
async def realtime_fund_nav(
    code: str = Path(description="基金代码，如 000001"),
):
    ds = FundDataSource()
    rows = await ds.fetch_fund_nav(code)
    if not rows:
        raise AppError(
            code=ErrorCode.DATA_SOURCE_ERROR,
            message=f"未能获取基金 {code} 的净值历史数据",
        )
    return ApiResponse.success({"fund_code": code, "items": rows})


@router.get(
    "/sectors/boards",
    summary="实时查询板块列表",
    description="直接调用 AkShare 获取行业/概念板块实时列表，不依赖数据库",
)
async def realtime_board_list(
    category: str = Query(
        default="industry",
        description="板块分类：industry（行业板块）或 concept（概念板块）",
    ),
):
    ds = SectorDataSource()
    if category == "industry":
        rows = await ds.fetch_industry_list()
    elif category == "concept":
        rows = await ds.fetch_concept_list()
    else:
        rows = []
        category = "unknown"

    return ApiResponse.success({
        "category": category,
        "items": rows,
        "total": len(rows),
    })


@router.get(
    "/sectors/{code}/history",
    summary="实时查询板块历史行情",
    description="直接调用 AkShare 查询指定板块的历史每日行情数据，不依赖数据库",
)
async def realtime_board_history(
    code: str = Path(description="板块代码，如 BK0456"),
    start_date: str | None = Query(
        default=None, description="开始日期，格式 YYYYMMDD，如 20260501"
    ),
    end_date: str | None = Query(
        default=None, description="结束日期，格式 YYYYMMDD，如 20260523"
    ),
):
    ds = SectorDataSource()
    rows = await ds.fetch_board_history(code, start_date, end_date)
    if not rows:
        raise AppError(
            code=ErrorCode.DATA_SOURCE_ERROR,
            message=f"未能获取板块 {code} 的历史行情数据",
        )
    return ApiResponse.success({
        "board_code": code,
        "items": rows,
        "total": len(rows),
    })
