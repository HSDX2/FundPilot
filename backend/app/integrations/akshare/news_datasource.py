"""Multi-source financial news data sources.

Sources:
  - eastmoney  (东方财富) : ak.stock_news_em()
  - jin10      (金十数据) : flash-api.jin10.com (Plan B direct scrape)
  - cls        (财联社)   : ak.stock_info_global_cls()
  - wallstreetcn (华尔街见闻) : ak.macro_info_ws()
"""

import asyncio
import logging
from typing import Any

import akshare as ak
import httpx

from app.integrations.base import with_retry

logger = logging.getLogger(__name__)

# ── Source name constants ──────────────────────────────────────────

SOURCE_EASTMONEY = "eastmoney"
SOURCE_JIN10 = "jin10"
SOURCE_CLS = "cls"
SOURCE_WALLSTREETCN = "wallstreetcn"

ALL_NEWS_SOURCES = [SOURCE_EASTMONEY, SOURCE_JIN10, SOURCE_CLS, SOURCE_WALLSTREETCN]

# ── Column mappings (AkShare column name → internal field name) ───

EASTMONEY_COLUMNS: dict[str, str] = {
    "新闻标题": "title",
    "新闻内容": "content",
    "发布时间": "published_at",
    "文章来源": "source",
    "新闻链接": "url",
    "关键词": "keywords",
}

CLS_COLUMNS: dict[str, str] = {
    "标题": "title",
    "内容": "content",
    "发布时间": "published_at",
    "来源": "source",
    "链接": "url",
}

WALLSTREETCN_COLUMNS: dict[str, str] = {
    "标题": "title",
    "内容": "content",
    "发布时间": "published_at",
    "来源": "source",
    "链接": "url",
}

# ── Helpers ────────────────────────────────────────────────────────


def _rename_columns(
    data: list[dict[str, Any]],
    mapping: dict[str, str],
) -> list[dict[str, Any]]:
    result = []
    for row in data:
        renamed = {}
        for ak_key, our_key in mapping.items():
            if ak_key in row:
                renamed[our_key] = row[ak_key]
        result.append(renamed)
    return result


# ── Data source ────────────────────────────────────────────────────


class NewsDataSource:
    """Multi-source financial news aggregation.

    Usage::

        ds = NewsDataSource()
        all_news = await ds.fetch_all()                    # all sources
        tier1 = await ds.fetch_all(["eastmoney", "jin10"]) # selected
    """

    @property
    def name(self) -> str:
        return "akshare_news"

    # ── Public API ──────────────────────────────────────────────

    async def fetch_news_list(self) -> list[dict[str, Any]]:
        """Backward-compatible: fetch East Money only."""
        return await self.fetch_eastmoney()

    async def fetch_all(
        self, sources: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch from all or specified sources concurrently.

        Args:
            sources: List of source names.  None means all sources.
        """
        if sources is None:
            sources = list(ALL_NEWS_SOURCES)

        tasks = []
        for source in sources:
            fn = self._get_fetch_fn(source)
            if fn is not None:
                tasks.append(fn())

        if not tasks:
            logger.warning("No valid news sources to fetch: %s", sources)
            return []

        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_records: list[dict[str, Any]] = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(
                    "News source fetch failed: %s — %s",
                    sources[i] if i < len(sources) else "?",
                    result,
                )
            else:
                all_records.extend(result)

        return all_records

    def _get_fetch_fn(self, source: str):
        return {
            SOURCE_EASTMONEY: self.fetch_eastmoney,
            SOURCE_JIN10: self.fetch_jin10,
            SOURCE_CLS: self.fetch_cls,
            SOURCE_WALLSTREETCN: self.fetch_wallstreetcn,
        }.get(source)

    # ── Individual source fetchers ───────────────────────────────

    async def fetch_eastmoney(self) -> list[dict[str, Any]]:
        """Fetch from East Money (东方财富)."""
        loop = asyncio.get_running_loop()

        def _sync() -> list[dict[str, Any]]:
            df = ak.stock_news_em()
            return df.to_dict(orient="records")

        raw = await with_retry(
            lambda: loop.run_in_executor(None, _sync),
            source_name="news_eastmoney",
        )
        records = _rename_columns(raw, EASTMONEY_COLUMNS)
        for r in records:
            r["source"] = SOURCE_EASTMONEY
        return records

    async def fetch_jin10(self) -> list[dict[str, Any]]:
        """Fetch from Jin10 flash API (金十数据).

        Calls https://flash-api.jin10.com/get_flash_list directly
        since Jin10 is not available in AkShare 1.18.63.
        """
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    "https://flash-api.jin10.com/get_flash_list",
                    params={
                        "channel": "-8200",
                        "vip": "1",
                        "max_time": "",
                    },
                    headers={
                        "User-Agent": (
                            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                            "AppleWebKit/537.36"
                        ),
                        "Referer": "https://flash.jin10.com/",
                        "Accept": "application/json",
                    },
                )
                resp.raise_for_status()
                body = resp.json()

            if body.get("code") != 200:
                logger.warning("Jin10 API returned code=%s", body.get("code"))
                return []

            items = body.get("data") or []
            records: list[dict[str, Any]] = []
            for item in items:
                if not isinstance(item, dict):
                    continue
                content = item.get("content") or item.get("title") or ""
                flash_id = item.get("id")
                url = (
                    f"https://flash.jin10.com/detail/{flash_id}"
                    if flash_id else ""
                )
                published = item.get("time") or item.get("pub_time") or ""
                records.append({
                    "title": (content[:120] + "...") if len(content) > 120 else content,
                    "content": content,
                    "url": url,
                    "source": SOURCE_JIN10,
                    "published_at": published if published else None,
                })
            return records
        except Exception as exc:
            logger.error("Jin10 fetch failed: %s", exc)
            return []

    async def fetch_cls(self) -> list[dict[str, Any]]:
        """Fetch from CLS (财联社)."""
        loop = asyncio.get_running_loop()

        def _sync() -> list[dict[str, Any]]:
            df = ak.stock_info_global_cls()
            if df is None or df.empty:
                return []
            return df.to_dict(orient="records")

        raw = await with_retry(
            lambda: loop.run_in_executor(None, _sync),
            source_name="news_cls",
        )
        records = _rename_columns(raw, CLS_COLUMNS)
        for r in records:
            r["source"] = SOURCE_CLS
        return records

    async def fetch_wallstreetcn(self) -> list[dict[str, Any]]:
        """Fetch from WallStreetCN (华尔街见闻)."""
        loop = asyncio.get_running_loop()

        def _sync() -> list[dict[str, Any]]:
            df = ak.macro_info_ws()
            if df is None or df.empty:
                return []
            return df.to_dict(orient="records")

        raw = await with_retry(
            lambda: loop.run_in_executor(None, _sync),
            source_name="news_wallstreetcn",
        )
        records = _rename_columns(raw, WALLSTREETCN_COLUMNS)
        for r in records:
            r["source"] = SOURCE_WALLSTREETCN
        return records
