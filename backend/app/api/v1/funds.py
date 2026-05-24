"""基金相关 API 路由."""

from datetime import date

from fastapi import APIRouter, Depends, Path, Query

from app.api.deps import get_fund_repo, get_fund_service
from app.core.errors import FundNotFoundError
from app.core.response import ApiResponse
from app.repositories.fund_repo import FundRepo
from app.schemas.fund import FundResponse
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
    service: FundService = Depends(get_fund_service),
):
    data = await service.search_funds(
        name=name, type_=type, company=company, page=page, page_size=page_size,
    )
    return ApiResponse.success(data.model_dump())


@router.get(
    "/{code}",
    summary="查询基金详情",
    description="根据基金代码查询基金基本信息",
)
async def get_fund(
    code: str = Path(description="基金代码，如 000001"),
    repo: FundRepo = Depends(get_fund_repo),
):
    fund = await repo.get_by_code(code)
    if fund is None:
        raise FundNotFoundError(code)
    return ApiResponse.success(
        FundResponse.model_validate(fund).model_dump()
    )


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

    data = await service.get_fund_nav_history(fund.id, start, end)
    return ApiResponse.success(data.model_dump())


@router.get(
    "/{code}/estimate",
    summary="查询基金实时估值",
    description="查询指定基金的最新盘中估值数据",
)
async def get_fund_estimate(
    code: str = Path(description="基金代码，如 000001"),
    repo: FundRepo = Depends(get_fund_repo),
    service: FundService = Depends(get_fund_service),
):
    fund = await repo.get_by_code(code)
    if fund is None:
        raise FundNotFoundError(code)

    estimate = await service.get_fund_estimate(fund.id)
    if estimate is None:
        return ApiResponse.success(data=None)
    return ApiResponse.success(estimate.model_dump())


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
    data = await service.get_batch_estimates(code_list)
    return ApiResponse.success(data.model_dump())
