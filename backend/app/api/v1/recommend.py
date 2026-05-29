"""推荐系统 API 路由."""

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query

from app.api.deps import (
    get_ai_provider_repo,
    get_fund_nav_repo,
    get_fund_repo,
    get_news_article_repo,
    get_prompt_setting_repo,
    get_sector_money_flow_repo,
    get_sector_repo,
    get_sector_snapshot_repo,
)
from app.core.errors import InvalidArgumentError
from app.core.response import ApiResponse
from app.repositories.analysis_repo import RecommendationRepo
from app.repositories.fund_repo import FundNavRepo, FundRepo
from app.repositories.news_repo import NewsArticleRepo
from app.repositories.sector_repo import (
    SectorMoneyFlowRepo,
    SectorRepo,
    SectorSnapshotRepo,
)
from app.repositories.system_repo import AIProviderRepo, PromptSettingRepo
from app.schemas.recommend import (
    DipBuyRequest,
    RecommendRequest,
    RecommendResponse,
)
from app.services.recommendation_service import RecommendationService

router = APIRouter(prefix="/recommend", tags=["推荐系统"])


from app.api.deps import get_db as _get_db
from sqlalchemy.ext.asyncio import AsyncSession


async def _get_rec_repo(
    session: AsyncSession = Depends(_get_db),
) -> RecommendationRepo:
    return RecommendationRepo(session)


def _get_recommend_svc(
    ai_provider_repo: AIProviderRepo = Depends(get_ai_provider_repo),
    prompt_setting_repo: PromptSettingRepo = Depends(get_prompt_setting_repo),
    fund_repo: FundRepo = Depends(get_fund_repo),
    fund_nav_repo: FundNavRepo = Depends(get_fund_nav_repo),
    sector_repo: SectorRepo = Depends(get_sector_repo),
    sector_snapshot_repo: SectorSnapshotRepo = Depends(get_sector_snapshot_repo),
    sector_money_flow_repo: SectorMoneyFlowRepo = Depends(
        get_sector_money_flow_repo,
    ),
    news_repo: NewsArticleRepo = Depends(get_news_article_repo),
    rec_repo: RecommendationRepo = Depends(_get_rec_repo),
) -> RecommendationService:
    return RecommendationService(
        ai_provider_repo=ai_provider_repo,
        prompt_setting_repo=prompt_setting_repo,
        fund_repo=fund_repo,
        fund_nav_repo=fund_nav_repo,
        sector_repo=sector_repo,
        sector_snapshot_repo=sector_snapshot_repo,
        sector_money_flow_repo=sector_money_flow_repo,
        news_repo=news_repo,
        recommendation_repo=rec_repo,
    )


@router.post("/top-picks", summary="综合推荐")
async def recommend_top_picks(
    body: RecommendRequest,
    svc: RecommendationService = Depends(_get_recommend_svc),
):
    """从全市场筛选当前最值得关注的基金和板块。"""
    items = await svc.top_picks(limit=body.limit, category=body.category)
    return ApiResponse.success(
        RecommendResponse(items=items, total=len(items)).model_dump(),
    )


@router.post("/dip-buy", summary="加仓推荐")
async def recommend_dip_buy(
    body: DipBuyRequest,
    svc: RecommendationService = Depends(_get_recommend_svc),
):
    """筛选因回调被低估、值得加仓的基金。"""
    items = await svc.dip_buy(
        limit=body.limit,
        max_drawdown=body.max_drawdown,
        min_consecutive_days=body.min_consecutive_days,
    )
    return ApiResponse.success(
        RecommendResponse(items=items, total=len(items)).model_dump(),
    )


@router.get("/history", summary="查询推荐历史")
async def list_recommendations(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    start_date: date | None = Query(
        default=None, description="筛选起始日期",
    ),
    end_date: date | None = Query(
        default=None, description="筛选结束日期",
    ),
    mode: str | None = Query(
        default=None, description="推荐模式：top_picks / dip_buy",
    ),
    svc: RecommendationService = Depends(_get_recommend_svc),
):
    items, total = await svc.list_recent(
        page=page, page_size=page_size,
        start_date=start_date, end_date=end_date,
        mode=mode,
    )
    out = []
    for item in items:
        out.append({
            "id": str(item.id),
            "date": str(item.date),
            "mode": item.mode,
            "type": item.rec_type,
            "action": item.action,
            "target_name": item.target_name,
            "target_code": item.target_code,
            "confidence": item.confidence,
            "reason_summary": item.reason_summary,
            "reason_detail": item.reason_detail,
            "risk_warning": item.risk_warning,
        })
    return ApiResponse.success({"items": out, "total": total})


@router.delete("/history", summary="批量删除推荐记录")
async def delete_recommendations(
    ids: str = Query(description="UUID 列表，逗号分隔"),
    svc: RecommendationService = Depends(_get_recommend_svc),
):
    id_list = []
    for raw in ids.split(","):
        raw = raw.strip()
        try:
            id_list.append(uuid.UUID(raw))
        except ValueError:
            raise InvalidArgumentError(f"无效 ID: {raw}")
    deleted = await svc._rec_repo.delete_by_ids(id_list)
    await svc._rec_repo.session.commit()
    return ApiResponse.success({"deleted": deleted})
