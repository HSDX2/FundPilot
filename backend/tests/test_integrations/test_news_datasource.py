"""Tests for NewsDataSource multi-source support."""

from unittest.mock import AsyncMock, patch

import pandas as pd
import pytest

from app.integrations.akshare.news_datasource import (
    SOURCE_CLS,
    SOURCE_EASTMONEY,
    SOURCE_JIN10,
    SOURCE_WALLSTREETCN,
    NewsDataSource,
)

# ── Fake httpx.AsyncClient for Jin10 tests ──────────────────────────


class _FakeResponse:
    """A fake httpx.Response that returns canned JSON."""

    def __init__(self, json_data: dict):
        self._json = json_data

    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict:
        return self._json


class _FakeAsyncClient:
    """A fake httpx.AsyncClient that supports async context manager."""

    def __init__(self):
        self.get = AsyncMock()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args) -> None:
        pass


def _jin10_response(code: int, data: list | None) -> _FakeResponse:
    return _FakeResponse({"code": code, "data": data})


def _make_client(response: _FakeResponse) -> _FakeAsyncClient:
    client = _FakeAsyncClient()
    client.get.return_value = response
    return client


class TestNewsDataSource:
    @pytest.mark.asyncio
    async def test_fetch_eastmoney_success(self):
        """stock_news_em should return renamed + source-tagged records."""
        ds = NewsDataSource()
        mock_data = pd.DataFrame({
            "新闻标题": ["Test Title"],
            "新闻内容": ["Test Content"],
            "发布时间": ["2026-05-24 10:00:00"],
            "文章来源": ["东方财富"],
            "新闻链接": ["http://example.com/news/1"],
            "关键词": ["test"],
        })
        with patch(
            "app.integrations.akshare.news_datasource.ak.stock_news_em",
            return_value=mock_data,
        ):
            result = await ds.fetch_eastmoney()
            assert len(result) == 1
            assert result[0]["title"] == "Test Title"
            assert result[0]["url"] == "http://example.com/news/1"
            assert result[0]["source"] == SOURCE_EASTMONEY

    @pytest.mark.asyncio
    async def test_fetch_eastmoney_empty(self):
        ds = NewsDataSource()
        with patch(
            "app.integrations.akshare.news_datasource.ak.stock_news_em",
            return_value=pd.DataFrame(),
        ):
            result = await ds.fetch_eastmoney()
            assert result == []

    @pytest.mark.asyncio
    async def test_fetch_eastmoney_exception(self):
        ds = NewsDataSource()
        with patch(
            "app.integrations.akshare.news_datasource.ak.stock_news_em",
            side_effect=RuntimeError("API error"),
        ):
            result = await ds.fetch_eastmoney()
            assert result == []

    @pytest.mark.asyncio
    async def test_fetch_cls_success(self):
        """stock_info_global_cls should return source-tagged records."""
        ds = NewsDataSource()
        mock_data = pd.DataFrame({
            "标题": ["CLS Title"],
            "内容": ["CLS Content"],
            "发布时间": ["2026-05-24 11:00:00"],
            "来源": ["财联社"],
            "链接": ["http://cls.cn/1"],
        })
        with patch(
            "app.integrations.akshare.news_datasource.ak.stock_info_global_cls",
            return_value=mock_data,
        ):
            result = await ds.fetch_cls()
            assert len(result) == 1
            assert result[0]["title"] == "CLS Title"
            assert result[0]["source"] == SOURCE_CLS

    @pytest.mark.asyncio
    async def test_fetch_cls_empty(self):
        ds = NewsDataSource()
        with patch(
            "app.integrations.akshare.news_datasource.ak.stock_info_global_cls",
            return_value=pd.DataFrame(),
        ):
            result = await ds.fetch_cls()
            assert result == []

    @pytest.mark.asyncio
    async def test_fetch_wallstreetcn_success(self):
        """macro_info_ws should return source-tagged records."""
        ds = NewsDataSource()
        mock_data = pd.DataFrame({
            "标题": ["WS Title"],
            "内容": ["WS Content"],
            "发布时间": ["2026-05-24 12:00:00"],
            "来源": ["华尔街见闻"],
            "链接": ["http://wallstreetcn.com/1"],
        })
        with patch(
            "app.integrations.akshare.news_datasource.ak.macro_info_ws",
            return_value=mock_data,
        ):
            result = await ds.fetch_wallstreetcn()
            assert len(result) == 1
            assert result[0]["title"] == "WS Title"
            assert result[0]["source"] == SOURCE_WALLSTREETCN

    @pytest.mark.asyncio
    async def test_fetch_jin10_success(self):
        """Jin10 API should parse flash list response."""
        ds = NewsDataSource()

        _make_response = _jin10_response(
            code=200,
            data=[
                {
                    "id": 12345,
                    "content": "美联储宣布降息50个基点",
                    "time": "2026-05-24 14:00:00",
                },
                {
                    "id": 12346,
                    "content": "A longer flash content " + "x" * 150,
                    "time": "",
                },
            ],
        )

        with patch(
            "app.integrations.akshare.news_datasource.httpx.AsyncClient",
            return_value=_make_client(_make_response),
        ):
            result = await ds.fetch_jin10()

            assert len(result) == 2
            assert result[0]["title"] == "美联储宣布降息50个基点"
            assert result[0]["content"] == "美联储宣布降息50个基点"
            assert result[0]["url"] == "https://flash.jin10.com/detail/12345"
            assert result[0]["source"] == SOURCE_JIN10
            assert result[0]["published_at"] == "2026-05-24 14:00:00"

            # Long content should be truncated in title
            assert result[1]["title"].endswith("...")

    @pytest.mark.asyncio
    async def test_fetch_jin10_error_code(self):
        """Non-200 code from Jin10 should return empty."""
        ds = NewsDataSource()

        with patch(
            "app.integrations.akshare.news_datasource.httpx.AsyncClient",
            return_value=_make_client(_jin10_response(code=500, data=None)),
        ):
            result = await ds.fetch_jin10()
            assert result == []

    @pytest.mark.asyncio
    async def test_fetch_jin10_http_error(self):
        """HTTP error from Jin10 should return empty list."""
        ds = NewsDataSource()

        client = _FakeAsyncClient()
        client.get = AsyncMock(side_effect=Exception("Connection error"))

        with patch(
            "app.integrations.akshare.news_datasource.httpx.AsyncClient",
            return_value=client,
        ):
            result = await ds.fetch_jin10()
            assert result == []

    # ── fetch_all ─────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_fetch_all_default_sources(self):
        """fetch_all() with no args should query all four sources."""
        ds = NewsDataSource()
        ds.fetch_eastmoney = AsyncMock(return_value=[
            {"title": "EM", "source": SOURCE_EASTMONEY, "url": "http://a"},
        ])
        ds.fetch_jin10 = AsyncMock(return_value=[
            {"title": "J10", "source": SOURCE_JIN10, "url": "http://b"},
        ])
        ds.fetch_cls = AsyncMock(return_value=[])
        ds.fetch_wallstreetcn = AsyncMock(return_value=[
            {"title": "WS", "source": SOURCE_WALLSTREETCN, "url": "http://c"},
        ])

        result = await ds.fetch_all()
        assert len(result) == 3
        sources = {r["source"] for r in result}
        assert sources == {SOURCE_EASTMONEY, SOURCE_JIN10, SOURCE_WALLSTREETCN}

        ds.fetch_eastmoney.assert_called_once()
        ds.fetch_jin10.assert_called_once()
        ds.fetch_cls.assert_called_once()
        ds.fetch_wallstreetcn.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_all_selected_sources(self):
        """fetch_all(['eastmoney', 'cls']) should only query those two."""
        ds = NewsDataSource()
        ds.fetch_eastmoney = AsyncMock(return_value=[
            {"title": "EM", "source": SOURCE_EASTMONEY, "url": "http://a"},
        ])
        ds.fetch_cls = AsyncMock(return_value=[
            {"title": "CLS", "source": SOURCE_CLS, "url": "http://b"},
        ])
        ds.fetch_jin10 = AsyncMock()
        ds.fetch_wallstreetcn = AsyncMock()

        result = await ds.fetch_all(sources=[SOURCE_EASTMONEY, SOURCE_CLS])
        assert len(result) == 2
        ds.fetch_jin10.assert_not_called()
        ds.fetch_wallstreetcn.assert_not_called()

    @pytest.mark.asyncio
    async def test_fetch_all_one_failure_does_not_block(self):
        """If one source fails, others still return data."""
        ds = NewsDataSource()
        ds.fetch_eastmoney = AsyncMock(return_value=[
            {"title": "EM", "source": SOURCE_EASTMONEY, "url": "http://a"},
        ])
        ds.fetch_jin10 = AsyncMock(side_effect=RuntimeError("fail"))
        ds.fetch_cls = AsyncMock(return_value=[])
        ds.fetch_wallstreetcn = AsyncMock(return_value=[])

        result = await ds.fetch_all()
        assert len(result) == 1
        assert result[0]["source"] == SOURCE_EASTMONEY

    # ── Backward compat ────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_fetch_news_list_backward_compat(self):
        """fetch_news_list() should delegate to fetch_eastmoney()."""
        ds = NewsDataSource()
        ds.fetch_eastmoney = AsyncMock(return_value=[
            {"title": "EM", "source": SOURCE_EASTMONEY, "url": "http://a"},
        ])
        result = await ds.fetch_news_list()
        assert len(result) == 1
        assert result[0]["source"] == SOURCE_EASTMONEY

    def test_name(self):
        ds = NewsDataSource()
        assert ds.name == "akshare_news"
