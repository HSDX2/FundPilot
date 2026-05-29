"""AkShare market sentiment data source."""

import asyncio
import logging
from datetime import date
from typing import Any

import akshare as ak

from app.integrations.base import BaseDataSource, DataSourceError, with_retry

logger = logging.getLogger(__name__)


class SentimentDataSource(BaseDataSource):
    """Fetches market sentiment indicators from AkShare."""

    name = "sentiment"

    async def fetch(self, **kwargs) -> list[dict[str, Any]]:
        """Fetch all sentiment data for a date (required by BaseDataSource)."""
        target_date = kwargs.get("target_date")
        result = await self.fetch_all_sentiment(target_date=target_date)
        return [result]

    async def _run_sync(self, fn) -> Any:
        """Run a synchronous AkShare function in a thread."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, fn)

    async def _fetch_with_retry(self, name: str, fn) -> list[dict]:
        """Run sync fn in executor with retry."""
        try:
            df = await with_retry(
                lambda: self._run_sync(fn),
                source_name=name,
            )
        except DataSourceError:
            return []
        if df is None or df.empty:
            return []
        return df.to_dict(orient="records")

    async def fetch_limit_up_pool(
        self, target_date: date | None = None,
    ) -> list[dict[str, Any]]:
        """涨停池 — limit-up stocks on a given date."""
        dt_str = (target_date or date.today()).strftime("%Y%m%d")
        return await self._fetch_with_retry(
            "limit_up",
            lambda: ak.stock_zt_pool_em(date=dt_str),
        )

    async def fetch_limit_down_pool(
        self, target_date: date | None = None,
    ) -> list[dict[str, Any]]:
        """跌停池 — limit-down stocks on a given date."""
        dt_str = (target_date or date.today()).strftime("%Y%m%d")
        return await self._fetch_with_retry(
            "limit_down",
            lambda: ak.stock_zt_pool_dtgc_em(date=dt_str),
        )

    async def fetch_limit_up_broken(
        self, target_date: date | None = None,
    ) -> list[dict[str, Any]]:
        """炸板池 — stocks that hit limit-up but did not hold."""
        dt_str = (target_date or date.today()).strftime("%Y%m%d")
        return await self._fetch_with_retry(
            "limit_up_broken",
            lambda: ak.stock_zt_pool_zbgc_em(date=dt_str),
        )

    async def fetch_north_bound_history(
        self,
    ) -> list[dict[str, Any]]:
        """北向资金历史 — daily north-bound capital flow history."""
        return await self._fetch_with_retry(
            "north_bound",
            lambda: ak.stock_hsgt_hist_em(),
        )

    async def fetch_north_bound_summary(
        self,
    ) -> list[dict[str, Any]]:
        """北向资金当日汇总."""
        return await self._fetch_with_retry(
            "north_bound_summary",
            lambda: ak.stock_hsgt_fund_flow_summary_em(),
        )

    async def fetch_margin_sse(self) -> list[dict[str, Any]]:
        """融资融券 — 沪市."""
        return await self._fetch_with_retry(
            "margin_sse",
            lambda: ak.stock_margin_sse(),
        )

    async def fetch_margin_szse(self) -> list[dict[str, Any]]:
        """融资融券 — 深市."""
        return await self._fetch_with_retry(
            "margin_szse",
            lambda: ak.stock_margin_szse(),
        )

    async def fetch_lhb_detail(
        self, target_date: date | None = None,
    ) -> list[dict[str, Any]]:
        """龙虎榜明细."""
        dt = target_date or date.today()
        return await self._fetch_with_retry(
            "lhb",
            lambda: ak.stock_lhb_detail_em(
                start_date=dt.strftime("%Y%m%d"),
                end_date=dt.strftime("%Y%m%d"),
            ),
        )

    async def fetch_a_spot(self) -> list[dict[str, Any]]:
        """A股实时行情 — 分页获取涨跌家数（替代 AkShare 慢速全量抓取）。"""
        import httpx

        headers = {
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://quote.eastmoney.com/",
        }
        base_params = {
            "ut": "bd1d9ddb04089700cf9c27f6f7426281",
            "fltt": "2", "invt": "2",
            "fs": "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048",
            "fields": "f2,f3,f4,f12,f14",
            "np": "1",
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            all_items = []
            for pn in range(1, 31):  # max 30 pages × 100 = 3000 stocks
                try:
                    params = dict(base_params, pn=str(pn), pz="100", po="1", fid="f3")
                    resp = await client.get(
                        "https://push2.eastmoney.com/api/qt/clist/get",
                        params=params, headers=headers,
                    )
                    items = resp.json().get("data", {}).get("diff", [])
                    if not items:
                        break
                    # 重命名字段为 AkShare 兼容格式，转换数值类型
                    for item in items:
                        item["最新价"] = item.pop("f2", None)
                        r = item.pop("f3", None)
                        item["涨跌幅"] = float(r) if r is not None and r != "-" else None
                        item["涨跌额"] = item.pop("f4", None)
                        item["代码"] = item.pop("f12", None)
                        item["名称"] = item.pop("f14", None)
                    all_items.extend(items)
                    await asyncio.sleep(0.2)
                except Exception:
                    break
            return all_items

    async def fetch_market_fund_flow(self) -> list[dict[str, Any]]:
        """市场资金流向 — 主力/超大单/大单/中单/小单."""
        return await self._fetch_with_retry(
            "fund_flow",
            lambda: ak.stock_market_fund_flow(),
        )

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
