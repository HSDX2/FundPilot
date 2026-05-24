import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class NewsArticle(TimestampMixin, Base):
    __tablename__ = "news_articles"

    title: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str | None] = mapped_column(String(32))
    url: Mapped[str | None] = mapped_column(Text, unique=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sentiment_score: Mapped[float | None] = mapped_column(Numeric(4, 2))


class NewsSectorLink(Base):
    """多对多关联：新闻与板块的关系。"""

    __tablename__ = "news_sector_links"

    news_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("news_articles.id"),
        primary_key=True,
    )
    sector_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sectors.id"),
        primary_key=True,
    )
    relevance_score: Mapped[float | None] = mapped_column(Numeric(4, 2))
