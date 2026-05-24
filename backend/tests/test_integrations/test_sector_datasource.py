"""Tests for SectorDataSource — AkShare calls are mocked.

All patching uses the import path within the datasource module
(``app.integrations.akshare.sector_datasource.ak``) instead of the
top-level ``akshare`` module because AkShare uses lazy attribute loading.
"""

import pandas as pd
import pytest

from app.integrations.akshare.sector_datasource import SectorDataSource

MOCK_MODULE = "app.integrations.akshare.sector_datasource.ak"


@pytest.fixture
def ds():
    return SectorDataSource()


class TestFetchIndustryList:
    async def test_success(self, mocker):
        """Industry board list should be mapped correctly."""
        mock_df = pd.DataFrame([
            {
                "板块名称": "半导体",
                "板块代码": "BK0811",
                "涨跌幅": 2.5,
            }
        ])
        mocker.patch(
            f"{MOCK_MODULE}.stock_board_industry_spot_em",
            return_value=mock_df,
            create=True,
        )

        result = await SectorDataSource().fetch_industry_list()

        assert len(result) == 1
        assert result[0]["name"] == "半导体"
        assert result[0]["code"] == "BK0811"
        assert result[0]["change_pct"] == 2.5

    async def test_empty(self, mocker):
        """Empty DataFrame should return empty list."""
        mocker.patch(
            f"{MOCK_MODULE}.stock_board_industry_spot_em",
            return_value=pd.DataFrame(),
            create=True,
        )

        result = await SectorDataSource().fetch_industry_list()
        assert result == []

    async def test_exception(self, mocker):
        """AkShare exception should return empty list."""
        mocker.patch(
            f"{MOCK_MODULE}.stock_board_industry_spot_em",
            side_effect=Exception("API error"),
            create=True,
        )

        result = await SectorDataSource().fetch_industry_list()
        assert result == []


class TestFetchConceptList:
    async def test_success(self, mocker):
        """Concept board list should be mapped correctly."""
        mock_df = pd.DataFrame([
            {"板块名称": "人工智能", "板块代码": "BK0800", "涨跌幅": 3.0}
        ])
        mocker.patch(
            f"{MOCK_MODULE}.stock_board_concept_spot_em",
            return_value=mock_df,
            create=True,
        )

        result = await SectorDataSource().fetch_concept_list()
        assert result[0]["name"] == "人工智能"

    async def test_exception(self, mocker):
        """AkShare exception should return empty list."""
        mocker.patch(
            f"{MOCK_MODULE}.stock_board_concept_spot_em",
            side_effect=Exception("error"),
            create=True,
        )
        result = await SectorDataSource().fetch_concept_list()
        assert result == []


class TestFetchBoardHistory:
    async def test_success(self, mocker):
        """Board history should be mapped correctly."""
        mock_df = pd.DataFrame([
            {
                "date": "2026-01-10",
                "开盘": 1000,
                "收盘": 1020,
                "最高": 1030,
                "最低": 990,
                "成交量": 1000000,
                "成交额": 5e8,
                "涨跌幅": 2.0,
            }
        ])
        mocker.patch(
            f"{MOCK_MODULE}.stock_board_industry_hist_em",
            return_value=mock_df,
            create=True,
        )

        result = await SectorDataSource().fetch_board_history("BK0811")
        assert len(result) == 1
        assert result[0]["close"] == 1020
        assert result[0]["change_pct"] == 2.0

    async def test_default_dates(self, mocker):
        """Default date range should be used when not provided."""
        mocker.patch(
            f"{MOCK_MODULE}.stock_board_industry_hist_em",
            return_value=pd.DataFrame(),
            create=True,
        )

        result = await SectorDataSource().fetch_board_history("BK0811")
        assert result == []


class TestFetchBoardCons:
    async def test_success(self, mocker):
        """Board constituents should be mapped correctly."""
        mock_df = pd.DataFrame([
            {"代码": "600519", "名称": "贵州茅台", "现价": 1800.0, "涨跌幅": 1.5}
        ])
        mocker.patch(
            f"{MOCK_MODULE}.stock_board_industry_cons_em",
            return_value=mock_df,
            create=True,
        )

        result = await SectorDataSource().fetch_board_cons("BK0811")
        assert result[0]["stock_code"] == "600519"

    async def test_exception(self, mocker):
        """AkShare exception should return empty list."""
        mocker.patch(
            f"{MOCK_MODULE}.stock_board_industry_cons_em",
            side_effect=Exception("error"),
            create=True,
        )
        result = await SectorDataSource().fetch_board_cons("BK0811")
        assert result == []
