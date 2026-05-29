"""AI Analysis API routes — sector reports, fund advice, news sentiment."""

import asyncio
import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_analysis_service, get_news_article_repo, get_sentiment_repo
from app.core.database import get_db
from app.core.errors import ErrorCode, InvalidArgumentError
from app.core.response import ApiResponse
from app.core.task_lock import sentiment_lock
from app.repositories.news_repo import NewsArticleRepo
from app.repositories.sentiment_repo import MarketSentimentRepo
from app.schemas.news import NewsArticleResponse
from app.schemas.analysis import (
    AnalysisReportListData,
    AnalysisReportResponse,
    BatchDeleteReportsRequest,
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
from app.tasks.analysis_tasks import run_news_sentiment_analysis_task

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
    description="对涨幅居前的 N 个板块批量生成分析报告，可按 category 筛选",
)
async def generate_all_reports(
    body: GenerateAllReportsRequest,
    service: AnalysisService = Depends(get_analysis_service),
):
    reports = await service.generate_all_sector_reports(
        report_type=body.report_type,
        limit=body.limit,
        sector_ids=[str(sid) for sid in body.sector_ids] if body.sector_ids else None,
        category=body.category,
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
    description="按类型、分类和日期查询历史分析报告",
)
async def list_reports(
    report_type: str = Query(
        default="daily",
        description="报告类型: daily / weekly / monthly",
    ),
    category: str | None = Query(
        default=None,
        description="板块分类: industry(行业) / concept(概念)",
    ),
    start_date: date | None = Query(
        default=None, description="筛选起始日期（含），如 2026-05-01",
    ),
    end_date: date | None = Query(
        default=None, description="筛选结束日期（含），如 2026-05-28",
    ),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    service: AnalysisService = Depends(get_analysis_service),
):
    rows, total = await service._report_repo.list_by_type_with_sector(
        report_type=report_type,
        category=category,
        start_date=start_date,
        end_date=end_date,
        page=page,
        page_size=page_size,
    )
    items_out = []
    for report, sector_name in rows:
        d = AnalysisReportResponse.model_validate(report).model_dump()
        d["sector_name"] = sector_name
        items_out.append(d)
    return ApiResponse.success(
        AnalysisReportListData(
            items=items_out,
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


@router.delete(
    "/reports/{report_id}",
    summary="删除分析报告",
)
async def delete_report(
    report_id: Annotated[str, Path(description="报告 UUID")],
    service: AnalysisService = Depends(get_analysis_service),
):
    try:
        rid = uuid.UUID(report_id)
    except ValueError:
        raise InvalidArgumentError("报告 ID 格式无效")

    deleted = await service._report_repo.delete_by_id(rid)
    if not deleted:
        return ApiResponse.error(
            ErrorCode.REPORT_NOT_FOUND, "报告不存在", status_code=404,
        )
    await service._report_repo.session.commit()
    return ApiResponse.success(None, message="报告已删除")


@router.post(
    "/reports/batch-delete",
    summary="批量删除分析报告",
)
async def batch_delete_reports(
    body: BatchDeleteReportsRequest,
    service: AnalysisService = Depends(get_analysis_service),
):
    deleted = await service._report_repo.delete_by_ids(
        [uid for uid in body.ids]
    )
    await service._report_repo.session.commit()
    return ApiResponse.success({"deleted": deleted}, message=f"已删除 {deleted} 份报告")


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
    # 补充基金编码和名称
    fund = await service._fund_repo.get(body.fund_id)
    fund_code = fund.code if fund else None
    fund_name = fund.name if fund else None
    d = FundAdviceResponse.model_validate(advice).model_dump()
    d["fund_code"] = fund_code
    d["fund_name"] = fund_name
    return ApiResponse.success(d)


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
    items_out = []
    for advice in advices:
        d = FundAdviceResponse.model_validate(advice).model_dump()
        # 补充基金编码和名称
        fund = await service._fund_repo.get(advice.fund_id)
        d["fund_code"] = fund.code if fund else None
        d["fund_name"] = fund.name if fund else None
        items_out.append(d)
    return ApiResponse.success(
        FundAdviceListData(
            items=items_out,
            total=len(items_out),
            page=1,
            page_size=len(items_out),
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
    fund_code: str | None = Query(
        default=None,
        description="按基金编码模糊搜索",
    ),
    start_date: date | None = Query(
        default=None, description="筛选起始日期（含），如 2026-05-01",
    ),
    end_date: date | None = Query(
        default=None, description="筛选结束日期（含），如 2026-05-28",
    ),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    service: AnalysisService = Depends(get_analysis_service),
):
    rows, total = await service._advice_repo.list_recent(
        page=page,
        page_size=page_size,
        action=action,
        fund_code=fund_code,
        start_date=start_date,
        end_date=end_date,
    )
    items_out = []
    for advice, fund_code_val, fund_name_val in rows:
        d = FundAdviceResponse.model_validate(advice).model_dump()
        d["fund_code"] = fund_code_val
        d["fund_name"] = fund_name_val
        items_out.append(d)
    return ApiResponse.success(
        FundAdviceListData(
            items=items_out,
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

@router.get(
    "/news/sentiment/status",
    summary="查询新闻情感分析任务状态",
    description="查看当前是否有分析任务正在执行",
)
async def sentiment_task_status():
    return ApiResponse.success(sentiment_lock.status)


@router.post(
    "/news/sentiment",
    summary="批量新闻情感分析",
    description="对最近未分析的新闻进行情感评分（后台任务，不阻塞请求）",
)
async def analyze_sentiment(
    body: BatchSentimentRequest,
):
    if await sentiment_lock.try_acquire("news_sentiment"):
        asyncio.create_task(
            run_news_sentiment_analysis_task(
                limit=body.limit,
                force=body.force,
                start_date=body.start_date,
                end_date=body.end_date,
            ),
        )
        return ApiResponse.success({
            "status": "started",
            "message": "新闻情绪分析任务已启动，可在后台继续处理",
        })
    return ApiResponse.success({
        "status": "running",
        "message": "新闻情绪分析任务正在执行中，请稍后再试",
    })


@router.post(
    "/news/{news_id}/sentiment",
    summary="重新分析单条新闻情绪",
    description="对指定新闻重新进行 AI 情绪分析，覆盖已有评分",
)
async def reanalyze_news_sentiment(
    news_id: str = Path(description="新闻 UUID"),
    service: AnalysisService = Depends(get_analysis_service),
    news_repo: NewsArticleRepo = Depends(get_news_article_repo),
):
    try:
        nid = uuid.UUID(news_id)
    except ValueError:
        raise InvalidArgumentError("新闻 ID 格式无效")

    await service.analyze_news_sentiment(nid)
    await news_repo.session.commit()
    article = await news_repo.get(nid)
    if article is None:
        from app.core.errors import NewsNotFoundError
        raise NewsNotFoundError(news_id)
    return ApiResponse.success(
        NewsArticleResponse.model_validate(article).model_dump(),
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


@router.delete(
    "/sentiment",
    summary="清空情绪历史数据",
    description="删除所有市场情绪历史记录。",
)
async def clear_sentiment(
    session: AsyncSession = Depends(get_db),
):
    repo = MarketSentimentRepo(session)
    count = await repo.delete_all()
    await session.commit()
    return ApiResponse.success({"deleted": count})
