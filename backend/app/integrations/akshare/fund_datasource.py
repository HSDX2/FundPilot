"""AkShare-based fund data source.

AkShare is a synchronous library. All public methods run blocking calls
in a thread pool executor to remain compatible with the async service layer.
"""

import asyncio
import logging
from datetime import date
from typing import Any

import akshare as ak

from app.integrations.base import with_retry

logger = logging.getLogger(__name__)

# Mapping from AkShare column names to our canonical field names.
# fund_name_em returns: 基金代码, 拼音缩写, 基金简称, 基金类型, 拼音全称
FUND_LIST_COLUMNS: dict[str, str] = {
    "基金代码": "code",
    "基金简称": "name",
    "基金类型": "type",
}

# fund_value_estimation_em has dynamic date-based columns. We parse them.
# Static columns:
ESTIMATE_STATIC_COLUMNS: dict[str, str] = {
    "基金代码": "fund_code",
    "基金名称": "fund_name",
    "估算偏差": "estimate_deviation",
}

ETF_LIST_COLUMNS: dict[str, str] = {
    "代码": "code",
    "名称": "name",
}

ETF_SPOT_COLUMNS: dict[str, str] = {
    "代码": "code",
    "名称": "name",
    "最新价": "price",
    "涨跌幅": "change_pct",
    "成交额": "turnover",
    "成交量": "volume",
}


def _rename_columns(
    data: list[dict[str, Any]],
    mapping: dict[str, str],
) -> list[dict[str, Any]]:
    """Rename dict keys according to a mapping. Unknown columns are dropped."""
    result = []
    for row in data:
        renamed = {}
        for ak_key, our_key in mapping.items():
            if ak_key in row:
                renamed[our_key] = row[ak_key]
        result.append(renamed)
    return result


class FundDataSource:
    """Fund data from AkShare."""

    @property
    def name(self) -> str:
        return "akshare_fund"

    async def fetch_fund_list(self) -> list[dict[str, Any]]:
        """Fetch all open-end fund list."""
        loop = asyncio.get_running_loop()

        def _sync() -> list[dict[str, Any]]:
            df = ak.fund_name_em()
            return df.to_dict(orient="records")

        raw = await with_retry(
            lambda: loop.run_in_executor(None, _sync),
            source_name=self.name,
        )
        return _rename_columns(raw, FUND_LIST_COLUMNS)

    @staticmethod
    def _parse_estimate_row(row: dict[str, Any]) -> dict[str, Any]:
        """Parse a row from fund_value_estimation_em into canonical fields."""
        result: dict[str, Any] = {}
        # Static columns
        for ak_key, our_key in ESTIMATE_STATIC_COLUMNS.items():
            if ak_key in row:
                result[our_key] = row[ak_key]

        # Dynamic date-based columns
        # Pattern: "{date}-估算数据-估算值", "{date}-估算数据-估算增长率",
        #          "{date}-公布数据-单位净值", "{date}-公布数据-日增长率",
        #          "{date}-单位净值" (previous day NAV)
        estimate_nav_key = None
        estimate_pct_key = None
        nav_key = None
        daily_pct_key = None
        prev_nav_key = None

        for col in row:
            if "-估算数据-估算值" in col:
                estimate_nav_key = col
            elif "-估算数据-估算增长率" in col:
                estimate_pct_key = col
            elif "-公布数据-单位净值" in col:
                nav_key = col
            elif "-公布数据-日增长率" in col:
                daily_pct_key = col
            elif "-单位净值" in col and "公布数据" not in col:
                prev_nav_key = col

        if estimate_nav_key:
            result["estimate_nav"] = row.get(estimate_nav_key)
        if estimate_pct_key:
            result["estimate_change_pct"] = row.get(estimate_pct_key)
        if nav_key:
            result["nav"] = row.get(nav_key)
        if daily_pct_key:
            result["daily_change_pct"] = row.get(daily_pct_key)
        if prev_nav_key:
            result["prev_nav"] = row.get(prev_nav_key)

        return result

    async def fetch_estimate_all(self) -> list[dict[str, Any]]:
        """Fetch real-time NAV estimates for all funds."""
        loop = asyncio.get_running_loop()

        def _sync() -> list[dict[str, Any]]:
            df = ak.fund_value_estimation_em()
            return df.to_dict(orient="records")

        raw = await with_retry(
            lambda: loop.run_in_executor(None, _sync),
            source_name=self.name,
        )
        return [self._parse_estimate_row(row) for row in raw]

    async def fetch_etf_list(self) -> list[dict[str, Any]]:
        """Fetch ETF fund list for populating funds table with type=ETF."""
        loop = asyncio.get_running_loop()

        def _sync() -> list[dict[str, Any]]:
            df = ak.fund_etf_spot_em()
            return df.to_dict(orient="records")

        raw = await with_retry(
            lambda: loop.run_in_executor(None, _sync),
            source_name=self.name,
        )
        mapped = _rename_columns(raw, ETF_LIST_COLUMNS)
        for record in mapped:
            record["type"] = "ETF"
        return mapped

    async def fetch_etf_spot(self) -> list[dict[str, Any]]:
        """Fetch ETF real-time spot data."""
        loop = asyncio.get_running_loop()

        def _sync() -> list[dict[str, Any]]:
            df = ak.fund_etf_spot_em()
            return df.to_dict(orient="records")

        raw = await with_retry(
            lambda: loop.run_in_executor(None, _sync),
            source_name=self.name,
        )
        return _rename_columns(raw, ETF_SPOT_COLUMNS)

    async def fetch_estimate_by_code(
        self, code: str
    ) -> dict[str, Any] | None:
        """Fetch real-time estimate for a single fund by code."""
        loop = asyncio.get_running_loop()

        def _sync() -> list[dict[str, Any]]:
            df = ak.fund_value_estimation_em()
            return df.to_dict(orient="records")

        raw = await with_retry(
            lambda: loop.run_in_executor(None, _sync),
            source_name=self.name,
        )
        for row in raw:
            if str(row.get("基金代码")) == code:
                return self._parse_estimate_row(row)
        return None

    async def fetch_fund_nav(
        self, code: str, start_date: date | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch historical NAV for a single fund.

        Args:
            code: Fund code.
            start_date: Earliest date to pull. If None, defaults to 1-year lookback.
                        Maximum lookback is 2 years from today.
        """
        loop = asyncio.get_running_loop()

        # Map start_date to AkShare period parameter
        today = date.today()
        if start_date is None:
            period = "1年"
        else:
            days_ago = (today - start_date).days
            if days_ago <= 30:
                period = "1月"
            elif days_ago <= 180:
                period = "6月"
            elif days_ago <= 365:
                period = "1年"
            elif days_ago <= 730:
                period = "3年"  # Closest option, capped to 2 years by filter
            else:
                period = "3年"  # Closest option, capped to 2 years by filter

        def _sync() -> list[dict[str, Any]]:
            df = ak.fund_open_fund_info_em(
                symbol=code, indicator="单位净值走势", period=period,
            )
            return df.to_dict(orient="records")

        raw = await with_retry(
            lambda: loop.run_in_executor(None, _sync),
            source_name=self.name,
        )

        # Hard cap: 2 years from today
        cutoff = max(
            today.replace(year=today.year - 2),
            start_date or today.replace(year=today.year - 1),
        )

        # AkShare returns: 净值日期, 单位净值, 日增长率
        result = []
        for row in raw:
            nav_date = row.get("净值日期")
            if nav_date is None:
                continue
            # Parse date if it's a string
            if isinstance(nav_date, str):
                try:
                    nav_date = date.fromisoformat(nav_date)
                except ValueError:
                    continue
            if nav_date < cutoff:
                continue
            result.append({
                "fund_code": code,
                "date": nav_date,
                "nav": row.get("单位净值"),
                "daily_change_pct": row.get("日增长率"),
            })
        return result
