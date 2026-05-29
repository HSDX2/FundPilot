"""Tests for SectorDataSource — AkShare calls are mocked.

All patching uses the import path within the datasource module
(``app.integrations.akshare.sector_datasource.ak``) instead of the
top-level ``akshare`` module because AkShare uses lazy attribute loading.
"""

import pandas as pd
import pytest

from app.integrations.akshare.sector_datasource import SectorDataSource
from app.integrations.base import DataSourceError

MOCK_MODULE = "app.integrations.akshare.sector_datasource.ak"


@pytest.fixture
def ds():
    return SectorDataSource()


class TestFetchIndustryList:
    async def test_success(self, mocker):
        """Industry board list merges name_ths + summary_ths."""
        names_df = pd.DataFrame([
            {"name": "半导体", "code": "881121"},
            {"name": "元件", "code": "881270"},
        ])
        stats_df = pd.DataFrame([
            {"板块": "半导体", "涨跌幅": 2.5, "均价": 1200.0,
             "总成交量": 1000, "总成交额": 5e8,
             "净流入": 1e8, "上涨家数": 20, "下跌家数": 10},
            {"板块": "元件", "涨跌幅": 7.85, "均价": 65.93,
             "总成交量": 2436, "总成交额": 1.6e9,
             "净流入": 3e8, "上涨家数": 30, "下跌家数": 1},
        ])
        mocker.patch(
            f"{MOCK_MODULE}.stock_board_industry_name_ths",
            return_value=names_df,
            create=True,
        )
        mocker.patch(
            f"{MOCK_MODULE}.stock_board_industry_summary_ths",
            return_value=stats_df,
            create=True,
        )

        result = await SectorDataSource().fetch_industry_list()

        assert len(result) == 2
        assert result[0]["name"] == "半导体"
        assert result[0]["code"] == "881121"
        assert result[0]["change_pct"] == 2.5
        assert result[1]["name"] == "元件"
        assert result[1]["change_pct"] == 7.85

    async def test_empty(self, mocker):
        """Empty DataFrames should return empty list."""
        mocker.patch(
            f"{MOCK_MODULE}.stock_board_industry_name_ths",
            return_value=pd.DataFrame(columns=["name", "code"]),
            create=True,
        )
        mocker.patch(
            f"{MOCK_MODULE}.stock_board_industry_summary_ths",
            return_value=pd.DataFrame(),
            create=True,
        )

        result = await SectorDataSource().fetch_industry_list()
        assert result == []

    async def test_exception(self, mocker):
        """AkShare exception should raise DataSourceError after retries exhausted."""
        mocker.patch(
            f"{MOCK_MODULE}.stock_board_industry_name_ths",
            side_effect=Exception("API error"),
            create=True,
        )

        with pytest.raises(DataSourceError, match="akshare_sector"):
            await SectorDataSource().fetch_industry_list()


class TestFetchConceptList:
    async def test_success(self, mocker):
        """Concept board list returns names + codes from THS."""
        mock_df = pd.DataFrame([
            {"name": "人工智能", "code": "308888"},
            {"name": "AI应用", "code": "309999"},
        ])
        mocker.patch(
            f"{MOCK_MODULE}.stock_board_concept_name_ths",
            return_value=mock_df,
            create=True,
        )

        result = await SectorDataSource().fetch_concept_list()
        assert len(result) == 2
        assert result[0]["name"] == "人工智能"
        assert result[0]["code"] == "308888"

    async def test_exception(self, mocker):
        """AkShare exception should raise DataSourceError after retries exhausted."""
        mocker.patch(
            f"{MOCK_MODULE}.stock_board_concept_name_ths",
            side_effect=Exception("error"),
            create=True,
        )

        with pytest.raises(DataSourceError, match="akshare_sector"):
            await SectorDataSource().fetch_concept_list()


class TestFetchBoardHistory:
    async def test_success_industry(self, mocker):
        """Industry board history uses THS index function."""
        mock_df = pd.DataFrame([
            {
                "日期": "2026-01-10",
                "开盘价": 1000.0,
                "收盘价": 1020.0,
                "最高价": 1030.0,
                "最低价": 990.0,
                "成交量": 1000000.0,
                "成交额": 5e8,
            }
        ])
        mocker.patch(
            f"{MOCK_MODULE}.stock_board_industry_index_ths",
            return_value=mock_df,
            create=True,
        )

        result = await SectorDataSource().fetch_board_history(
            "半导体", category="industry",
        )
        assert len(result) == 1
        assert result[0]["close"] == 1020.0
        assert result[0]["open"] == 1000.0

    async def test_success_concept(self, mocker):
        """Concept board history uses THS concept index."""
        mock_df = pd.DataFrame([
            {
                "日期": "2026-01-10",
                "开盘价": 950.0,
                "收盘价": 970.0,
                "最高价": 980.0,
                "最低价": 940.0,
                "成交量": 500000.0,
                "成交额": 2e8,
            }
        ])
        mocker.patch(
            f"{MOCK_MODULE}.stock_board_concept_index_ths",
            return_value=mock_df,
            create=True,
        )

        result = await SectorDataSource().fetch_board_history(
            "AI应用", category="concept",
        )
        assert len(result) == 1
        assert result[0]["close"] == 970.0

    async def test_default_dates(self, mocker):
        """Default date range should be used when not provided."""
        mocker.patch(
            f"{MOCK_MODULE}.stock_board_industry_index_ths",
            return_value=pd.DataFrame(),
            create=True,
        )

        result = await SectorDataSource().fetch_board_history("半导体")
        assert result == []


class TestFetchBoardCons:
    async def test_raises_error(self, mocker):
        """Board constituents unavailable — push2 API blocked."""
        with pytest.raises(DataSourceError, match="board constituents"):
            await SectorDataSource().fetch_board_cons("BK0811")


class TestFetchSectorFundFlow:
    async def test_industry_success(self, mocker):
        """Industry fund flow uses THS source — push2 API blocked fallback."""
        mock_df = pd.DataFrame([
            {"行业": "半导体", "净额": "1.23亿"},
            {"行业": "元件", "净额": "-5000.00万"},
        ])
        mocker.patch(
            f"{MOCK_MODULE}.stock_fund_flow_industry",
            return_value=mock_df,
            create=True,
        )

        result = await SectorDataSource().fetch_sector_fund_flow(
            indicator="今日", sector_type="行业资金流",
        )
        assert len(result) == 2
        assert result[0]["name"] == "半导体"
        assert result[0]["main_force_net_inflow"] == pytest.approx(1.23e8)
        assert result[0]["middle_net_inflow"] is None
        assert result[0]["small_net_inflow"] is None
        assert result[1]["name"] == "元件"
        assert result[1]["main_force_net_inflow"] == pytest.approx(-5e7)

    async def test_concept_success(self, mocker):
        """Concept fund flow uses THS source."""
        mock_df = pd.DataFrame([
            {"行业": "人工智能", "净额": "2.00亿"},
        ])
        mocker.patch(
            f"{MOCK_MODULE}.stock_fund_flow_concept",
            return_value=mock_df,
            create=True,
        )

        result = await SectorDataSource().fetch_sector_fund_flow(
            indicator="今日", sector_type="概念资金流",
        )
        assert len(result) == 1
        assert result[0]["name"] == "人工智能"
        assert result[0]["main_force_net_inflow"] == pytest.approx(2e8)

    async def test_empty(self, mocker):
        """Empty DataFrame returns empty list."""
        mocker.patch(
            f"{MOCK_MODULE}.stock_fund_flow_industry",
            return_value=pd.DataFrame(),
            create=True,
        )

        result = await SectorDataSource().fetch_sector_fund_flow()
        assert result == []

    async def test_indicator_mapping(self, mocker):
        """Indicator '5日' maps to THS '5日排行'."""
        mock_patch = mocker.patch(
            f"{MOCK_MODULE}.stock_fund_flow_industry",
            return_value=pd.DataFrame(),
            create=True,
        )

        await SectorDataSource().fetch_sector_fund_flow(indicator="5日")
        mock_patch.assert_called_once_with("5日排行")

    async def test_exception(self, mocker):
        """AkShare exception should raise DataSourceError after retries exhausted."""
        mocker.patch(
            f"{MOCK_MODULE}.stock_fund_flow_industry",
            side_effect=Exception("THS error"),
            create=True,
        )

        with pytest.raises(DataSourceError, match="akshare_sector"):
            await SectorDataSource().fetch_sector_fund_flow()


class TestFetchSectorFundFlowRange:
    async def test_success_with_date_filter(self, mocker):
        """Historical fund flow filters records >= start_date."""
        from datetime import date

        mock_df = pd.DataFrame([
            {
                "日期": "2026-05-20",
                "主力净流入-净额": 1e8,
                "中单净流入-净额": -2e7,
                "小单净流入-净额": 5e7,
            },
            {
                "日期": "2026-05-21",
                "主力净流入-净额": 2e8,
                "中单净流入-净额": -3e7,
                "小单净流入-净额": 4e7,
            },
            {
                "日期": "2026-05-22",
                "主力净流入-净额": 3e8,
                "中单净流入-净额": -1e7,
                "小单净流入-净额": 6e7,
            },
        ])
        mocker.patch(
            f"{MOCK_MODULE}.stock_sector_fund_flow_hist",
            return_value=mock_df,
            create=True,
        )

        result = await SectorDataSource().fetch_sector_fund_flow_range(
            "半导体", date(2026, 5, 21),
        )
        assert len(result) == 2
        assert result[0]["date"] == date(2026, 5, 21)
        assert result[0]["name"] == "半导体"
        assert result[0]["main_force_net_inflow"] == 2e8
        assert result[0]["middle_net_inflow"] == -3e7
        assert result[0]["small_net_inflow"] == 4e7

    async def test_empty_returns_empty(self, mocker):
        """Empty DataFrame returns empty list."""
        from datetime import date

        mocker.patch(
            f"{MOCK_MODULE}.stock_sector_fund_flow_hist",
            return_value=pd.DataFrame(),
            create=True,
        )

        result = await SectorDataSource().fetch_sector_fund_flow_range(
            "半导体", date(2026, 1, 1),
        )
        assert result == []

    async def test_exception(self, mocker):
        """AkShare exception should raise DataSourceError."""
        from datetime import date

        mocker.patch(
            f"{MOCK_MODULE}.stock_sector_fund_flow_hist",
            side_effect=Exception("push2his error"),
            create=True,
        )

        with pytest.raises(DataSourceError, match="akshare_sector"):
            await SectorDataSource().fetch_sector_fund_flow_range(
                "半导体", date(2026, 1, 1),
            )
