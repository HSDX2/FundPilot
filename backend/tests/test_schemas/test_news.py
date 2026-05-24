"""Tests for news Pydantic schemas."""

from datetime import datetime
from uuid import uuid4

from app.schemas.news import NewsArticleListData, NewsArticleResponse


class TestNewsArticleResponse:
    def test_basic(self):
        data = NewsArticleResponse(
            id=uuid4(),
            title="Test Article",
            content="Some content",
            source="eastmoney",
            url="https://example.com",
            published_at=datetime(2026, 5, 23),
            sentiment_score=0.5,
        )
        assert data.title == "Test Article"
        assert data.sentiment_score == 0.5

    def test_optional_fields(self):
        data = NewsArticleResponse(
            id=uuid4(),
            title="Minimal",
        )
        assert data.content is None
        assert data.source is None


class TestNewsArticleListData:
    def test_basic(self):
        items = [
            NewsArticleResponse(id=uuid4(), title="A"),
            NewsArticleResponse(id=uuid4(), title="B"),
        ]
        data = NewsArticleListData(items=items, total=2, page=1, page_size=20)
        assert data.total == 2
        assert len(data.items) == 2
