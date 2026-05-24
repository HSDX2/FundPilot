"""新闻相关 API 路由."""

import uuid

from fastapi import APIRouter, Depends, Path, Query

from app.api.deps import get_news_article_repo
from app.core.errors import NewsNotFoundError
from app.core.response import ApiResponse
from app.repositories.news_repo import NewsArticleRepo
from app.schemas.news import NewsArticleListData, NewsArticleResponse

router = APIRouter(prefix="/news", tags=["新闻"])


@router.get(
    "",
    summary="查询新闻列表",
    description="分页查询新闻列表，支持按关键词、来源、时间范围筛选",
)
async def list_news(
    keyword: str | None = Query(default=None, description="关键词搜索"),
    source: str | None = Query(default=None, description="来源筛选"),
    start: str | None = Query(
        default=None, description="开始时间，ISO 格式",
    ),
    end: str | None = Query(
        default=None, description="结束时间，ISO 格式",
    ),
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(
        default=20, ge=1, le=100, description="每页数量",
    ),
    repo: NewsArticleRepo = Depends(get_news_article_repo),
):
    from datetime import datetime

    start_dt = datetime.fromisoformat(start) if start else None
    end_dt = datetime.fromisoformat(end) if end else None

    items, total = await repo.search(
        keyword=keyword,
        source=source,
        start=start_dt,
        end=end_dt,
        page=page,
        page_size=page_size,
    )
    data = NewsArticleListData(
        items=[NewsArticleResponse.model_validate(n) for n in items],
        total=total,
        page=page,
        page_size=page_size,
    )
    return ApiResponse.success(data.model_dump())


@router.get(
    "/{news_id}",
    summary="查询新闻详情",
    description="根据新闻 ID 查询新闻详情",
)
async def get_news(
    news_id: str = Path(description="新闻 UUID"),
    repo: NewsArticleRepo = Depends(get_news_article_repo),
):
    try:
        nid = uuid.UUID(news_id)
    except ValueError:
        from app.core.errors import InvalidArgumentError
        raise InvalidArgumentError("新闻 ID 格式无效")

    article = await repo.get(nid)
    if article is None:
        raise NewsNotFoundError(news_id)
    return ApiResponse.success(
        NewsArticleResponse.model_validate(article).model_dump()
    )
