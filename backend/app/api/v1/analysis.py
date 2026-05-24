"""AI Analysis API routes — sector reports, fund advice, news sentiment."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query

from app.api.deps import get_analysis_service, get_sentiment_repo
from app.core.errors import ErrorCode, InvalidArgumentError
from app.core.response import ApiResponse
from app.repositories.sentiment_repo import MarketSentimentRepo
from app.schemas.analysis import (
    AnalysisReportListData,
    AnalysisReportResponse,
    BatchGenerateAdviceRequest,
    BatchSentimentRequest,
    FundAdviceListData,
    FundAdviceResponse,
    GenerateAdviceRequest,
    GenerateAllReportsRequest,
    GenerateReportRequest,
    MarketSentimentListData,
    MarketSentimentResponse,
    NewsSentimentResponse,
)
from app.services.analysis_service import AnalysisService

router = APIRouter(prefix="/analysis", tags=["AI Analysis"])


# ── Sector Reports ────────────────────────────────────────────────────

@router.post(
    "/reports/generate",
    summary="生成单板块分析报告",
    description="对指定板块生成 AI 分析报告（日/周/月），使用当前激活的 AI Provider",
)
async def generate_report(
    body: GenerateReportRequest,
    service: AnalysisService = Depends(get_analysis_service),
):
    report = await service.generate_sector_report(
        sector_id=body.sector_id,
        report_type=body.report_type,
    )
    return ApiResponse.success(
        AnalysisReportResponse.model_validate(report).model_dump(),
    )


@router.post(
    "/reports/generate-all",
    summary="批量生成板块分析报告",
    description="对涨幅居前的 N 个板块批量生成分析报告",
)
async def generate_all_reports(
    body: GenerateAllReportsRequest,
    service: AnalysisService = Depends(get_analysis_service),
):
    reports = await service.generate_all_sector_reports(
        report_type=body.report_type,
        limit=body.limit,
    )
    return ApiResponse.success(
        AnalysisReportListData(
            items=[AnalysisReportResponse.model_validate(r) for r in reports],
            total=len(reports),
            page=1,
            page_size=len(reports),
        ).model_dump(),
    )


@router.get(
    "/reports",
    summary="查询分析报告列表",
    description="按类型和日期查询历史分析报告",
)
async def list_reports(
    report_type: str = Query(
        default="daily",
        description="报告类型: daily / weekly / monthly",
    ),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    service: AnalysisService = Depends(get_analysis_service),
):
    items, total = await service._report_repo.list_by_type(
        report_type=report_type,
        page=page,
        page_size=page_size,
    )
    return ApiResponse.success(
        AnalysisReportListData(
            items=[AnalysisReportResponse.model_validate(i) for i in items],
            total=total,
            page=page,
            page_size=page_size,
        ).model_dump(),
    )


@router.get(
    "/reports/latest",
    summary="查询最新分析报告",
    description="获取指定类型的最新一份分析报告",
)
async def get_latest_report(
    report_type: str = Query(
        default="daily",
        description="报告类型: daily / weekly / monthly",
    ),
    service: AnalysisService = Depends(get_analysis_service),
):
    report = await service._report_repo.get_latest_by_type(report_type)
    if report is None:
        return ApiResponse.success(data=None, message="No reports found")
    return ApiResponse.success(
        AnalysisReportResponse.model_validate(report).model_dump(),
    )


@router.get(
    "/reports/{report_id}",
    summary="查询报告详情",
)
async def get_report(
    report_id: Annotated[str, Path(description="报告 UUID")],
    service: AnalysisService = Depends(get_analysis_service),
):
    try:
        rid = uuid.UUID(report_id)
    except ValueError:
        raise InvalidArgumentError("报告 ID 格式无效")

    report = await service._report_repo.get(rid)
    if report is None:
        return ApiResponse.error(
            ErrorCode.REPORT_NOT_FOUND, "报告不存在", status_code=404,
        )
    return ApiResponse.success(
        AnalysisReportResponse.model_validate(report).model_dump(),
    )


# ── Fund Advice ───────────────────────────────────────────────────────

@router.post(
    "/advice/generate",
    summary="生成基金操作建议",
    description=(
        "对指定基金生成 AI 操作建议（buy/hold/reduce/redeem），"
        "使用当前激活的 AI Provider"
    ),
)
async def generate_advice(
    body: GenerateAdviceRequest,
    service: AnalysisService = Depends(get_analysis_service),
):
    advice = await service.generate_fund_advice(body.fund_id)
    return ApiResponse.success(
        FundAdviceResponse.model_validate(advice).model_dump(),
    )


@router.post(
    "/advice/generate-batch",
    summary="批量生成基金操作建议",
    description="对多个基金批量生成操作建议",
)
async def generate_batch_advice(
    body: BatchGenerateAdviceRequest,
    service: AnalysisService = Depends(get_analysis_service),
):
    fund_ids_str = [str(fid) for fid in body.fund_ids]
    advices = await service.generate_batch_fund_advice(fund_ids_str)
    return ApiResponse.success(
        FundAdviceListData(
            items=[FundAdviceResponse.model_validate(a) for a in advices],
            total=len(advices),
            page=1,
            page_size=len(advices),
        ).model_dump(),
    )


@router.get(
    "/advice",
    summary="查询基金操作建议列表",
    description="分页查询历史操作建议，可按 action 筛选",
)
async def list_advice(
    action: str | None = Query(
        default=None,
        description="筛选操作类型: buy / hold / reduce / redeem",
    ),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    service: AnalysisService = Depends(get_analysis_service),
):
    items, total = await service._advice_repo.list_recent(
        page=page,
        page_size=page_size,
        action=action,
    )
    return ApiResponse.success(
        FundAdviceListData(
            items=[FundAdviceResponse.model_validate(i) for i in items],
            total=total,
            page=page,
            page_size=page_size,
        ).model_dump(),
    )


@router.get(
    "/advice/{advice_id}",
    summary="查询操作建议详情",
)
async def get_advice(
    advice_id: Annotated[str, Path(description="建议 UUID")],
    service: AnalysisService = Depends(get_analysis_service),
):
    try:
        aid = uuid.UUID(advice_id)
    except ValueError:
        raise InvalidArgumentError("建议 ID 格式无效")

    advice = await service._advice_repo.get(aid)
    if advice is None:
        return ApiResponse.error(
            ErrorCode.ADVICE_NOT_FOUND, "建议不存在", status_code=404,
        )
    return ApiResponse.success(
        FundAdviceResponse.model_validate(advice).model_dump(),
    )


# ── News Sentiment ────────────────────────────────────────────────────

@router.post(
    "/news/sentiment",
    summary="批量新闻情感分析",
    description="对最近未分析的新闻进行情感评分",
)
async def analyze_sentiment(
    body: BatchSentimentRequest,
    service: AnalysisService = Depends(get_analysis_service),
):
    count = await service.batch_analyze_sentiment(limit=body.limit)
    return ApiResponse.success(
        NewsSentimentResponse(processed=count).model_dump(),
    )


# ── Market Sentiment ───────────────────────────────────────────────────


@router.get(
    "/sentiment",
    summary="查询市场情绪指标",
    description="获取每日市场情绪数据，包含涨停/跌停、北向资金、融资融券等",
)
async def list_sentiment(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    repo: MarketSentimentRepo = Depends(get_sentiment_repo),
):
    items = await repo.list(skip=(page - 1) * page_size, limit=page_size)
    total = await repo.count()
    return ApiResponse.success(
        MarketSentimentListData(
            items=[MarketSentimentResponse.model_validate(i) for i in items],
            total=total,
            page=page,
            page_size=page_size,
        ).model_dump(),
    )


@router.get(
    "/sentiment/latest",
    summary="查询最新市场情绪",
    description="获取最近一个交易日的市场情绪综合评分",
)
async def get_latest_sentiment(
    repo: MarketSentimentRepo = Depends(get_sentiment_repo),
):
    from sqlalchemy import select

    from app.models.sentiment import MarketSentiment

    stmt = (
        select(MarketSentiment)
        .order_by(MarketSentiment.date.desc())
        .limit(1)
    )
    result = await repo.session.execute(stmt)
    latest = result.scalar_one_or_none()
    if latest is None:
        return ApiResponse.success(data=None, message="No sentiment data yet")
    return ApiResponse.success(
        MarketSentimentResponse.model_validate(latest).model_dump(),
    )
