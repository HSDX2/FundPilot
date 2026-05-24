from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class NewsArticleResponse(BaseModel):
    id: UUID
    title: str
    content: str | None = None
    source: str | None = None
    url: str | None = None
    published_at: datetime | None = None
    sentiment_score: float | None = None

    model_config = {"from_attributes": True}


class NewsArticleListData(BaseModel):
    items: list[NewsArticleResponse]
    total: int
    page: int
    page_size: int
