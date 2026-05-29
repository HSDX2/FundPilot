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

# Mapping from fund_individual_basic_info_xq item names to our canonical fields
FUND_BASIC_INFO_MAP: dict[str, str] = {
    "成立时间": "established_date",
    "最新规模": "scale",
    "基金公司": "company",
    "基金经理": "fund_manager",
}

# Mapping from fund_info_ths (同花顺) item names to our canonical fields
FUND_BASIC_INFO_MAP_THS: dict[str, str] = {
    "成立日期": "established_date",
    "份额规模": "scale",
    "基金管理人": "company",
    "基金经理": "fund_manager",
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

    async def fetch_fund_basic_info(self, code: str) -> dict[str, Any] | None:
        """Fetch basic info for a single fund (company, manager, scale, etc.).

        Uses Xueqiu's fund detail API via AkShare.  Returns None if the
        API call fails or returns no data.
        """
        import pandas as pd

        loop = asyncio.get_running_loop()

        def _sync() -> pd.DataFrame:
            return ak.fund_individual_basic_info_xq(symbol=code)

        try:
            df: pd.DataFrame = await loop.run_in_executor(None, _sync)
        except Exception:
            logger.debug("fund_individual_basic_info_xq failed for %s", code)
            return None

        if df is None or df.empty:
            return None

        import re

        info: dict[str, Any] = {}
        for _, row in df.iterrows():
            item_name = str(row.get("item", ""))
            value = row.get("value")
            field = FUND_BASIC_INFO_MAP.get(item_name)
            if not field or value is None or str(value) == "nan":
                continue
            if field == "scale":
                # "26.44亿" → extract numeric part (in 亿), store as 亿
                match = re.search(r"([\d.]+)\s*([亿万])?", str(value))
                if match:
                    num = float(match.group(1))
                    unit = match.group(2)
                    info[field] = num * 10000 if unit == "万" else num
            elif field == "established_date":
                # "2001-12-18" → date object
                try:
                    info[field] = date.fromisoformat(str(value))
                except (ValueError, TypeError):
                    info[field] = None
            else:
                info[field] = str(value)
        return info if info else None

    async def fetch_fund_basic_info_ths(self, code: str) -> dict[str, Any] | None:
        """Fetch basic info for a single fund via 同花顺 (Ths) API.

        Works for both ETF and regular open-end funds. Falls back gracefully
        if the fund is not found on 同花顺.
        """
        loop = asyncio.get_running_loop()

        def _sync():
            return ak.fund_info_ths(symbol=code)

        try:
            df: pd.DataFrame = await loop.run_in_executor(None, _sync)
        except Exception:
            logger.debug("fund_info_ths failed for %s", code)
            return None

        if df is None or df.empty:
            return None

        import re

        info: dict[str, Any] = {}
        for _, row in df.iterrows():
            item_name = str(row.get("字段", ""))
            value = row.get("值")
            field = FUND_BASIC_INFO_MAP_THS.get(item_name)
            if not field or value is None or str(value) == "nan":
                continue
            if field == "scale":
                # "4.13亿份（2026-03-31）" or "3.28亿份"
                # Extract number before 亿份, store in 亿份 (no conversion needed)
                match = re.search(r"([\d.]+)\s*亿份", str(value))
                if match:
                    info[field] = float(match.group(1))
            elif field == "established_date":
                try:
                    info[field] = date.fromisoformat(str(value))
                except (ValueError, TypeError):
                    info[field] = None
            else:
                info[field] = str(value)
        return info if info else None

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

    async def _fetch_open_fund_nav(
        self, code: str, cutoff: date, period: str,
    ) -> list[dict[str, Any]]:
        """Fetch NAV via fund_open_fund_info_em (普通开放式基金)."""
        loop = asyncio.get_running_loop()

        def _sync() -> list[dict[str, Any]]:
            df = ak.fund_open_fund_info_em(
                symbol=code, indicator="单位净值走势", period=period,
            )
            return df.to_dict(orient="records")

        raw = await asyncio.wait_for(
            with_retry(
                lambda: loop.run_in_executor(None, _sync),
                source_name=self.name,
            ),
            timeout=30,
        )
        return self._parse_nav_rows(code, cutoff, raw, "单位净值", "日增长率")

    async def _fetch_etf_nav(
        self, code: str, cutoff: date,
    ) -> list[dict[str, Any]]:
        """Fetch NAV via fund_etf_fund_info_em (ETF 基金)."""
        loop = asyncio.get_running_loop()

        def _sync() -> list[dict[str, Any]]:
            df = ak.fund_etf_fund_info_em(fund=code)
            return df.to_dict(orient="records")

        raw = await asyncio.wait_for(
            with_retry(
                lambda: loop.run_in_executor(None, _sync),
                source_name=self.name,
            ),
            timeout=30,
        )
        return self._parse_nav_rows(code, cutoff, raw, "单位净值", "日增长率")

    @staticmethod
    def _parse_nav_rows(
        code: str,
        cutoff: date,
        raw: list[dict[str, Any]],
        nav_col: str,
        daily_change_col: str,
    ) -> list[dict[str, Any]]:
        """Parse AkShare NAV rows into canonical format."""
        result = []
        for row in raw:
            nav_date = row.get("净值日期")
            if nav_date is None:
                continue
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
                "nav": row.get(nav_col),
                "daily_change_pct": row.get(daily_change_col),
            })
        return result

    async def fetch_fund_nav(
        self, code: str, start_date: date | None = None,
        skip_etf: bool = False,
    ) -> list[dict[str, Any]]:
        """Fetch historical NAV for a single fund.

        先走开放式基金 API，若最新数据距今天超过 2 天（可能数据不全），
        则补走 ETF API 合并缺失日期，确保数据完整。

        Args:
            code: Fund code.
            start_date: Earliest date to pull.  If None, fetch all available
                        history (default period by AkShare).
            skip_etf: 跳过 ETF API 兜底（非 ETF 基金可避免无意义重试）。
        """
        today = date.today()

        if start_date is None:
            period = "3年"
            cutoff = date(2000, 1, 1)  # 拉取全部可用历史
        else:
            days_ago = (today - start_date).days
            if days_ago <= 30:
                period = "1月"
            elif days_ago <= 180:
                period = "6月"
            elif days_ago <= 365:
                period = "1年"
            else:
                period = "3年"
            cutoff = date(2000, 1, 1)  # 不设过滤，由 period 控制范围

        # 1. 先走开放式基金 API
        primary_data: list[dict[str, Any]] = []
        try:
            primary_data = await self._fetch_open_fund_nav(code, cutoff, period)
        except Exception:
            logger.debug("open-end fund NAV API failed for %s, trying ETF API", code)

        # 2. 检查数据完整度：最新日期距今天 > 2 天时，补走 ETF API 合并
        if primary_data:
            dates = [r["date"] for r in primary_data if r.get("date") is not None]
            if dates:
                latest = max(dates)
                if (today - latest).days <= 2:
                    return primary_data  # 数据已完整，无需补
                logger.debug(
                    "open-end fund NAV latest=%s, today=%s (gap=%d), "
                    "will try ETF API for missing data",
                    latest, today, (today - latest).days,
                )
        else:
            logger.debug(
                "open-end fund NAV API returned no data for %s, trying ETF API", code,
            )

        # 3. 补走 ETF API，合并缺失日期的数据（非 ETF 基金可跳过）
        if not skip_etf:
            try:
                etf_data = await self._fetch_etf_nav(code, cutoff)
                if etf_data:
                    existing_dates = {r["date"] for r in primary_data if r.get("date") is not None}
                    for row in etf_data:
                        d = row.get("date")
                        if d is not None and d not in existing_dates:
                            primary_data.append(row)
                            existing_dates.add(d)
                    logger.debug(
                        "ETF API merged %d new rows for %s",
                        len(etf_data) - (len(primary_data) - len(existing_dates)),
                        code,
                    )
            except Exception:
                if not primary_data:
                    logger.exception("ETF fund NAV API also failed for %s", code)

        return primary_data
