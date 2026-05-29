"""Tests for FundDataSource — AkShare calls are mocked."""

import pandas as pd
import pytest

from app.integrations.akshare.fund_datasource import FundDataSource
from app.integrations.base import DataSourceError

MOCK_MODULE = "app.integrations.akshare.fund_datasource.ak"


class TestFetchFundList:
    async def test_success(self, mocker):
        """AkShare fund list should be mapped correctly."""
        mock_df = pd.DataFrame([
            {
                "基金代码": "000001",
                "基金简称": "Test Fund",
                "基金类型": "股票型",
            }
        ])
        mocker.patch(
            f"{MOCK_MODULE}.fund_name_em",
            return_value=mock_df,
            create=True,
        )

        result = await FundDataSource().fetch_fund_list()

        assert len(result) == 1
        assert result[0]["code"] == "000001"
        assert result[0]["name"] == "Test Fund"
        assert result[0]["type"] == "股票型"

    async def test_empty(self, mocker):
        """Empty DataFrame should return empty list."""
        mocker.patch(
            f"{MOCK_MODULE}.fund_name_em",
            return_value=pd.DataFrame(),
            create=True,
        )

        result = await FundDataSource().fetch_fund_list()
        assert result == []

    async def test_akshare_exception(self, mocker):
        """AkShare exception should raise DataSourceError after retries exhausted."""
        mocker.patch(
            f"{MOCK_MODULE}.fund_name_em",
            side_effect=Exception("Connection error"),
            create=True,
        )

        with pytest.raises(DataSourceError, match="akshare_fund"):
            await FundDataSource().fetch_fund_list()


class TestFetchEtfSpot:
    async def test_success(self, mocker):
        """ETF spot data should be mapped correctly."""
        mock_df = pd.DataFrame([
            {
                "代码": "510050",
                "名称": "上证50ETF",
                "最新价": 2.50,
                "涨跌幅": 1.23,
            }
        ])
        mocker.patch(
            f"{MOCK_MODULE}.fund_etf_spot_em",
            return_value=mock_df,
            create=True,
        )

        result = await FundDataSource().fetch_etf_spot()

        assert len(result) == 1
        assert result[0]["code"] == "510050"
        assert result[0]["name"] == "上证50ETF"


class TestFetchFundNav:
    async def test_success(self, mocker):
        """Fund NAV data should be mapped correctly."""
        mock_df = pd.DataFrame([
            {
                "净值日期": "2026-01-10",
                "单位净值": 1.5,
                "日增长率": 0.5,
            }
        ])
        mocker.patch(
            f"{MOCK_MODULE}.fund_open_fund_info_em",
            return_value=mock_df,
            create=True,
        )

        result = await FundDataSource().fetch_fund_nav("000001")

        assert len(result) == 1
        assert result[0]["fund_code"] == "000001"
        assert result[0]["nav"] == 1.5
        assert result[0]["daily_change_pct"] == 0.5
