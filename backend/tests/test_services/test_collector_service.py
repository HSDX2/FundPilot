"""Tests for CollectorService — orchestration logic."""

from unittest.mock import AsyncMock

from app.services.collector_service import CollectorService, CollectResult


class TestCollectFundList:
    async def test_collect_fund_list_success(self):
        """Collect fund list should filter to focus types and call repo."""
        mock_ds = AsyncMock()
        mock_ds.fetch_fund_list.return_value = [
            {"code": "000001", "name": "Stock Fund", "type": "股票型"},
            {"code": "000002", "name": "Bond Fund", "type": "债券型"},
            {"code": "000003", "name": "ETF Fund", "type": "ETF"},
        ]

        mock_repo = AsyncMock()
        mock_repo.batch_upsert.return_value = (2, 0)

        service = CollectorService(fund_ds=mock_ds, fund_repo=mock_repo)
        result = await service.collect_fund_list()

        assert result.records_added == 2
        mock_ds.fetch_fund_list.assert_called_once()

    async def test_collect_fund_list_empty(self):
        """Empty response from data source should return error result."""
        mock_ds = AsyncMock()
        mock_ds.fetch_fund_list.return_value = []

        service = CollectorService(fund_ds=mock_ds)
        result = await service.collect_fund_list()

        assert result.records_added == 0
        assert len(result.errors) > 0

    async def test_collect_fund_list_no_repo(self):
        """Without a repo, should log but not crash."""
        mock_ds = AsyncMock()
        mock_ds.fetch_fund_list.return_value = [
            {"code": "000001", "name": "A", "type": "股票型"}
        ]

        service = CollectorService(fund_ds=mock_ds, fund_repo=None)
        result = await service.collect_fund_list()

        assert result.records_added == 1

    async def test_collect_fund_list_no_matching_types(self):
        """When no records match focus types, should return 0."""
        mock_ds = AsyncMock()
        mock_ds.fetch_fund_list.return_value = [
            {"code": "000001", "name": "Bond", "type": "债券型"},
            {"code": "000002", "name": "Money", "type": "货币型"},
        ]

        mock_repo = AsyncMock()
        mock_repo.batch_upsert.return_value = (0, 0)
        service = CollectorService(fund_ds=mock_ds, fund_repo=mock_repo)
        result = await service.collect_fund_list()

        assert result.records_added == 0


class TestCollectEstimates:
    async def test_collect_fund_estimates_success(self):
        """Fund estimate collection should call batch_upsert."""
        from uuid import uuid4

        mock_ds = AsyncMock()
        mock_ds.fetch_estimate_all.return_value = [
            {"fund_code": "000001", "estimate_nav": 1.23, "estimate_change_pct": 0.5},
        ]

        mock_repo = AsyncMock()
        mock_repo.batch_upsert.return_value = (1, 0)

        mock_fund_repo = AsyncMock()
        mock_fund_repo.get_all.return_value = [
            type("Fund", (), {"id": uuid4(), "code": "000001"})(),
        ]

        service = CollectorService(
            fund_ds=mock_ds, fund_estimate_repo=mock_repo, fund_repo=mock_fund_repo,
        )
        result = await service.collect_fund_estimates()

        assert result.records_added == 1

    async def test_collect_fund_estimates_empty(self):
        """Empty estimate data should return empty result."""
        mock_ds = AsyncMock()
        mock_ds.fetch_estimate_all.return_value = []

        mock_repo = AsyncMock()
        mock_fund_repo = AsyncMock()

        service = CollectorService(
            fund_ds=mock_ds, fund_estimate_repo=mock_repo, fund_repo=mock_fund_repo,
        )
        result = await service.collect_fund_estimates()

        assert result.records_added == 0
        assert len(result.errors) == 0

    async def test_collect_fund_estimates_no_repo(self):
        """Without a repo, should return error."""
        mock_ds = AsyncMock()

        service = CollectorService(fund_ds=mock_ds, fund_estimate_repo=None)
        result = await service.collect_fund_estimates()

        assert len(result.errors) > 0


class TestCollectEtfSpot:
    async def test_collect_etf_spot_success(self):
        """ETF spot collection should add timestamps and call repo."""
        mock_ds = AsyncMock()
        mock_ds.fetch_etf_spot.return_value = [
            {"code": "510050", "name": "Test ETF", "price": 1.23},
        ]

        mock_repo = AsyncMock()
        mock_repo.get_by_code.return_value = None

        service = CollectorService(
            fund_ds=mock_ds, fund_repo=mock_repo
        )
        result = await service.collect_etf_spot()

        assert result.records_updated == 0

    async def test_collect_etf_spot_empty(self):
        """Empty ETF data should return error."""
        mock_ds = AsyncMock()
        mock_ds.fetch_etf_spot.return_value = []

        service = CollectorService(fund_ds=mock_ds)
        result = await service.collect_etf_spot()

        assert result.records_added == 0
        assert len(result.errors) > 0

    async def test_collect_etf_spot_no_repo(self):
        """Without a repo, should not crash."""
        mock_ds = AsyncMock()
        mock_ds.fetch_etf_spot.return_value = [
            {"code": "510050", "name": "Test ETF", "price": 1.23},
        ]

        service = CollectorService(
            fund_ds=mock_ds, fund_repo=None
        )
        result = await service.collect_etf_spot()

        assert result.records_added == 1


class TestCollectSectorList:
    async def test_success(self):
        """Sector list should fetch industry + concept and persist."""
        mock_ds = AsyncMock()
        mock_ds.fetch_industry_list.return_value = [
            {"code": "BK001", "name": "半导体"},
        ]
        mock_ds.fetch_concept_list.return_value = [
            {"code": "BK101", "name": "AI概念"},
        ]

        mock_repo = AsyncMock()
        mock_repo.batch_upsert.side_effect = [(1, 0), (1, 0)]

        service = CollectorService(
            sector_ds=mock_ds, sector_repo=mock_repo
        )
        result = await service.collect_sector_list()

        assert result.records_added == 2
        # Verify category was added
        call1 = mock_repo.batch_upsert.call_args_list[0][0][0]
        assert call1[0]["category"] == "industry"
        call2 = mock_repo.batch_upsert.call_args_list[1][0][0]
        assert call2[0]["category"] == "concept"

    async def test_no_repo(self):
        """Without a repo, should not crash."""
        mock_ds = AsyncMock()
        mock_ds.fetch_industry_list.return_value = [
            {"code": "BK001", "name": "半导体"},
        ]
        mock_ds.fetch_concept_list.return_value = []

        service = CollectorService(sector_ds=mock_ds, sector_repo=None)
        result = await service.collect_sector_list()

        assert result.records_added == 1


class TestCollectNews:
    async def test_collect_news_empty(self):
        """Empty news data should return error."""
        mock_ds = AsyncMock()
        mock_ds.fetch_all.return_value = []

        mock_repo = AsyncMock()
        mock_repo.batch_upsert.return_value = (0, 0)

        service = CollectorService(
            news_ds=mock_ds, news_repo=mock_repo,
        )
        result = await service.collect_news()

        assert result.records_added == 0
        assert len(result.errors) > 0
        mock_ds.fetch_all.assert_called_once_with(sources=None)

    async def test_collect_news_success(self):
        """News collection should call batch_upsert."""
        mock_ds = AsyncMock()
        mock_ds.fetch_all.return_value = [
            {"title": "Test", "url": "http://example.com/1"},
        ]

        mock_repo = AsyncMock()
        mock_repo.batch_upsert.return_value = (1, 0)

        service = CollectorService(
            news_ds=mock_ds, news_repo=mock_repo,
        )
        result = await service.collect_news()

        assert result.records_added == 1
        mock_repo.batch_upsert.assert_called_once()

    async def test_collect_news_no_repo(self):
        """Without a repo, should return error."""
        mock_ds = AsyncMock()
        mock_ds.fetch_all.return_value = [
            {"title": "Test", "url": "http://example.com/1"},
        ]

        service = CollectorService(news_ds=mock_ds, news_repo=None)
        result = await service.collect_news()

        assert len(result.errors) > 0

    async def test_collect_news_with_sources(self):
        """collect_news(sources=[...]) should pass sources to datasource."""
        mock_ds = AsyncMock()
        mock_ds.fetch_all.return_value = [
            {"title": "EM", "url": "http://a", "source": "eastmoney"},
        ]

        mock_repo = AsyncMock()
        mock_repo.batch_upsert.return_value = (1, 0)

        service = CollectorService(
            news_ds=mock_ds, news_repo=mock_repo,
        )
        result = await service.collect_news(sources=["eastmoney", "jin10"])

        assert result.records_added == 1
        mock_ds.fetch_all.assert_called_once_with(
            sources=["eastmoney", "jin10"]
        )


class TestCollectResult:
    def test_collect_result_defaults(self):
        result = CollectResult()
        assert result.records_added == 0
        assert result.records_updated == 0
        assert result.errors == []

    def test_collect_result_to_dict(self):
        result = CollectResult(records_added=5, errors=["err"])
        d = result.to_dict()
        assert d["records_added"] == 5
        assert d["errors"] == ["err"]
