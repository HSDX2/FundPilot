"""AkShare market sentiment data source."""

import logging
from datetime import date
from typing import Any

import akshare as ak

from app.integrations.base import BaseDataSource, with_retry

logger = logging.getLogger(__name__)


class SentimentDataSource(BaseDataSource):
    """Fetches market sentiment indicators from AkShare."""

    name = "sentiment"

    async def fetch(self, **kwargs) -> list[dict[str, Any]]:
        """Fetch all sentiment data for a date (required by BaseDataSource)."""
        target_date = kwargs.get("target_date")
        result = await self.fetch_all_sentiment(target_date=target_date)
        return [result]

    async def fetch_limit_up_pool(
        self, target_date: date | None = None,
    ) -> list[dict[str, Any]]:
        """涨停池 — limit-up stocks on a given date."""
        dt_str = (target_date or date.today()).strftime("%Y%m%d")

        def _call():
            return ak.stock_zt_pool_em(date=dt_str)

        df = await with_retry(_call, source_name=self.name)
        if df is None or df.empty:
            return []
        return df.to_dict(orient="records")

    async def fetch_limit_down_pool(
        self, target_date: date | None = None,
    ) -> list[dict[str, Any]]:
        """跌停池 — limit-down stocks on a given date."""
        dt_str = (target_date or date.today()).strftime("%Y%m%d")

        def _call():
            return ak.stock_zt_pool_dtgc_em(date=dt_str)

        df = await with_retry(_call, source_name=self.name)
        if df is None or df.empty:
            return []
        return df.to_dict(orient="records")

    async def fetch_limit_up_broken(
        self, target_date: date | None = None,
    ) -> list[dict[str, Any]]:
        """炸板池 — stocks that hit limit-up but did not hold."""
        dt_str = (target_date or date.today()).strftime("%Y%m%d")

        def _call():
            return ak.stock_zt_pool_zbgc_em(date=dt_str)

        df = await with_retry(_call, source_name=self.name)
        if df is None or df.empty:
            return []
        return df.to_dict(orient="records")

    async def fetch_north_bound_history(
        self,
    ) -> list[dict[str, Any]]:
        """北向资金历史 — daily north-bound capital flow history."""

        def _call():
            return ak.stock_hsgt_hist_em()

        df = await with_retry(_call, source_name=self.name)
        if df is None or df.empty:
            return []
        return df.to_dict(orient="records")

    async def fetch_north_bound_summary(
        self,
    ) -> list[dict[str, Any]]:
        """北向资金当日汇总."""

        def _call():
            return ak.stock_hsgt_fund_flow_summary_em()

        df = await with_retry(_call, source_name=self.name)
        if df is None or df.empty:
            return []
        return df.to_dict(orient="records")

    async def fetch_margin_sse(self) -> list[dict[str, Any]]:
        """融资融券 — 沪市."""

        def _call():
            return ak.stock_margin_sse()

        df = await with_retry(_call, source_name=self.name)
        if df is None or df.empty:
            return []
        return df.to_dict(orient="records")

    async def fetch_margin_szse(self) -> list[dict[str, Any]]:
        """融资融券 — 深市."""

        def _call():
            return ak.stock_margin_szse()

        df = await with_retry(_call, source_name=self.name)
        if df is None or df.empty:
            return []
        return df.to_dict(orient="records")

    async def fetch_lhb_detail(
        self, target_date: date | None = None,
    ) -> list[dict[str, Any]]:
        """龙虎榜明细."""
        dt = target_date or date.today()
        dt_str = dt.strftime("%Y%m%d")

        def _call():
            return ak.stock_lhb_detail_em(
                start_date=dt_str, end_date=dt_str,
            )

        df = await with_retry(_call, source_name=self.name)
        if df is None or df.empty:
            return []
        return df.to_dict(orient="records")

    async def fetch_a_spot(self) -> list[dict[str, Any]]:
        """A股实时行情 — 用于统计涨跌家数."""

        def _call():
            return ak.stock_zh_a_spot_em()

        df = await with_retry(_call, source_name=self.name)
        if df is None or df.empty:
            return []
        return df.to_dict(orient="records")

    async def fetch_market_fund_flow(self) -> list[dict[str, Any]]:
        """市场资金流向 — 主力/超大单/大单/中单/小单."""

        def _call():
            return ak.stock_market_fund_flow()

        df = await with_retry(_call, source_name=self.name)
        if df is None or df.empty:
            return []
        return df.to_dict(orient="records")

    async def fetch_all_sentiment(
        self, target_date: date | None = None,
    ) -> dict[str, Any]:
        """Collect all sentiment data for a given date.

        Returns a dict with keys: limit_up, limit_down, limit_up_broken,
        north_bound, margin_sse, margin_szse, lhb, a_spot, fund_flow.
        Each key maps to list[dict] or None on failure.
        """
        dt = target_date or date.today()
        result: dict[str, Any] = {}

        fetchers = [
            ("limit_up", lambda: self.fetch_limit_up_pool(dt)),
            ("limit_down", lambda: self.fetch_limit_down_pool(dt)),
            ("limit_up_broken", lambda: self.fetch_limit_up_broken(dt)),
            ("north_bound", self.fetch_north_bound_history),
            ("margin_sse", self.fetch_margin_sse),
            ("margin_szse", self.fetch_margin_szse),
            ("lhb", lambda: self.fetch_lhb_detail(dt)),
            ("a_spot", self.fetch_a_spot),
            ("fund_flow", self.fetch_market_fund_flow),
        ]

        for key, fetcher in fetchers:
            try:
                result[key] = await fetcher()
            except Exception:
                logger.exception("Failed to fetch sentiment data: %s", key)
                result[key] = None

        return result
