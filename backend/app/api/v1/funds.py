"""基金相关 API 路由."""

from datetime import date

from fastapi import APIRouter, Depends, Path, Query

from app.api.deps import get_fund_repo, get_fund_service
from app.core.errors import ErrorCode, FundNotFoundError
from app.core.response import ApiResponse
from app.core.task_lock import collect_lock
from app.repositories.fund_repo import FundRepo
from app.schemas.fund import (
    CollectDataRequest,
    CollectDataResponse,
    FundResponse,
)
from app.services.fund_service import FundService

router = APIRouter(prefix="/funds", tags=["基金"])


@router.get(
    "",
    summary="查询基金列表",
    description="分页查询基金列表，支持按名称、类型、基金公司筛选",
)
async def list_funds(
    page: int = Query(default=1, ge=1, description="页码，从 1 开始"),
    page_size: int = Query(
        default=20, ge=1, le=100, description="每页数量，最大 100"
    ),
    type: str | None = Query(
        default=None,
        description=(
            "基金类型编码：stock(股票型) / mixed(混合型-偏股/灵活等) / "
            "index(指数型-股票等) / etf(ETF) / "
            "bond(债券型) / monetary(货币型) / qdii(QDII)"
        ),
    ),
    company: str | None = Query(default=None, description="基金公司名称筛选"),
    name: str | None = Query(default=None, description="基金名称模糊搜索"),
    sort_by: str | None = Query(
        default=None,
        description="排序字段：latest_change_pct（最新涨跌幅）",
    ),
    sort_order: str = Query(
        default="desc",
        description="排序方向：asc（升序）/ desc（降序），默认 desc",
    ),
    watched_only: bool = Query(
        default=False, description="是否只显示已关注的基金",
    ),
    service: FundService = Depends(get_fund_service),
):
    data = await service.search_funds(
        name=name, type_=type, company=company, page=page, page_size=page_size,
        sort_by=sort_by, sort_order=sort_order, watched_only=watched_only,
    )
    return ApiResponse.success(data.model_dump())


@router.get(
    "/{code}",
    summary="查询基金详情",
    description="根据基金代码查询基金基本信息",
)
async def get_fund(
    code: str = Path(description="基金代码，如 000001"),
    service: FundService = Depends(get_fund_service),
):
    fund = await service.get_fund_by_code(code)
    if fund is None:
        raise FundNotFoundError(code)
    return ApiResponse.success(fund.model_dump())


@router.get(
    "/{code}/nav",
    summary="查询基金净值历史",
    description="查询指定基金的净值历史数据，支持日期范围筛选",
)
async def get_fund_nav(
    code: str = Path(description="基金代码，如 000001"),
    start_date: str | None = Query(
        default=None, description="开始日期，格式 YYYY-MM-DD",
    ),
    end_date: str | None = Query(
        default=None, description="结束日期，格式 YYYY-MM-DD",
    ),
    repo: FundRepo = Depends(get_fund_repo),
    service: FundService = Depends(get_fund_service),
):
    fund = await repo.get_by_code(code)
    if fund is None:
        raise FundNotFoundError(code)

    start = date.fromisoformat(start_date) if start_date else None
    end = date.fromisoformat(end_date) if end_date else None

    data = await service.get_fund_nav_history(fund.id, fund.code, start, end)
    return ApiResponse.success(data.model_dump())


@router.get(
    "/{code}/estimate",
    summary="查询基金实时估值",
    description="查询指定基金的最新盘中估值数据",
)
async def get_fund_estimate(
    code: str = Path(description="基金代码，如 000001"),
    service: FundService = Depends(get_fund_service),
):
    estimate = await service.get_fund_estimate(code)
    return ApiResponse.success(data=estimate)


@router.get(
    "/estimates/batch",
    summary="批量查询基金估值",
    description="根据多个基金代码批量查询最新估值，代码用逗号分隔",
)
async def get_batch_estimates(
    codes: str = Query(
        ..., description="基金代码列表，逗号分隔，如 000001,000011",
    ),
    service: FundService = Depends(get_fund_service),
):
    code_list = [c.strip() for c in codes.split(",") if c.strip()]
    items = await service.get_batch_estimates(code_list)
    return ApiResponse.success({"items": items})


@router.post(
    "/{code}/collect-nav",
    summary="采集基金净值数据",
    description="从数据源采集基金的历史净值和涨跌幅数据",
)
async def collect_fund_nav(
    code: str = Path(description="基金代码，如 000001"),
    body: CollectDataRequest = CollectDataRequest(),
    service: FundService = Depends(get_fund_service),
):
    lock_key = f"fund:{code}:{body.mode}"
    if not await collect_lock.try_acquire(lock_key, f"collect-fund-nav-{code}-{body.mode}"):
        return ApiResponse.error(
            code=ErrorCode.TASK_RUNNING,
            message=f"基金 {code} 的「{body.mode}」采集任务正在执行中，请稍后重试",
        )
    try:
        if body.mode == "all":
            result = await service.collect_nav_all(code, start_date=body.start_date)
        else:
            result = await service.collect_nav_incremental(code)
    finally:
        collect_lock.release(lock_key)
    return ApiResponse.success(CollectDataResponse(**result).model_dump())
