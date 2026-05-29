"""Multi-source financial news data sources.

Sources:
  - eastmoney  (东方财富) : East Money search API (general keywords, paginated)
  - jin10      (金十数据) : flash-api.jin10.com (currently unavailable)
  - cls        (财联社)   : ak.stock_info_global_cls()
  - wallstreetcn (华尔街见闻) : api-one.wallstcn.com live feed
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any

import akshare as ak
import httpx

from app.integrations.base import DataSourceError, with_retry

logger = logging.getLogger(__name__)

# ── Source name constants ──────────────────────────────────────────

SOURCE_EASTMONEY = "eastmoney"
SOURCE_JIN10 = "jin10"
SOURCE_CLS = "cls"
SOURCE_WALLSTREETCN = "wallstreetcn"

ALL_NEWS_SOURCES = [SOURCE_EASTMONEY, SOURCE_JIN10, SOURCE_CLS, SOURCE_WALLSTREETCN]

# ── Column mappings (AkShare column name → internal field name) ───

CLS_COLUMNS: dict[str, str] = {
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


def _normalize_datetime(records: list[dict[str, Any]]) -> None:
    """Convert published_at from string to datetime in-place."""
    for r in records:
        val = r.get("published_at")
        if isinstance(val, str):
            for fmt in (
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d %H:%M",
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%dT%H:%M:%SZ",
                "%Y-%m-%d",
            ):
                try:
                    r["published_at"] = datetime.strptime(val, fmt)
                    break
                except ValueError:
                    continue
            else:
                r["published_at"] = None


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

        # 每个数据源独立超时，挂掉的源不影响其他源的结果
        timed_tasks = [
            asyncio.wait_for(coro, timeout=45.0)
            for coro in tasks
        ]
        results = await asyncio.gather(*timed_tasks, return_exceptions=True)

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

    # East Money search keywords — broad financial terms for wide coverage
    _EM_KEYWORDS = ["A股行情", "财经新闻", "基金市场"]

    async def fetch_eastmoney(self) -> list[dict[str, Any]]:
        """Fetch from East Money search API using general financial keywords.

        Calls the same search API that powers so.eastmoney.com, searching
        with broad keywords and paginating 2 pages × 50 items each to get
        ~300 articles per run (before cross-keyword dedup).
        """
        all_records: list[dict[str, Any]] = []
        seen_urls: set[str] = set()

        async with httpx.AsyncClient(timeout=20.0) as client:
            for keyword in self._EM_KEYWORDS:
                for page in (1, 2):
                    records = await self._fetch_em_page(client, keyword, page)
                    for r in records:
                        url = r.get("url")
                        if url and url not in seen_urls:
                            seen_urls.add(url)
                            all_records.append(r)

        logger.info(
            "East Money: %d articles from %d keywords × 2 pages",
            len(all_records), len(self._EM_KEYWORDS),
        )
        return all_records

    async def _fetch_em_page(
        self, client: httpx.AsyncClient, keyword: str, page: int,
    ) -> list[dict[str, Any]]:
        """Fetch a single page from East Money search API."""
        inner = {
            "uid": "",
            "keyword": keyword,
            "type": ["cmsArticleWebOld"],
            "client": "web",
            "clientType": "web",
            "clientVersion": "curr",
            "param": {
                "cmsArticleWebOld": {
                    "searchScope": "default",
                    "sort": "default",
                    "pageIndex": page,
                    "pageSize": 50,
                    "preTag": "<em>",
                    "postTag": "</em>",
                },
            },
        }
        params = {
            "cb": "jQuery",
            "param": json.dumps(inner, ensure_ascii=False),
            "_": str(int(datetime.now().timestamp() * 1000)),
        }
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/142.0.0.0 Safari/537.36"
            ),
            "Referer": "https://so.eastmoney.com/",
            "Accept": "*/*",
        }

        resp = await client.get(
            "https://search-api-web.eastmoney.com/search/jsonp",
            params=params, headers=headers,
        )
        text = resp.text
        try:
            json_str = text[text.find("(") + 1 : text.rfind(")")]
            data = json.loads(json_str)
        except (json.JSONDecodeError, ValueError):
            logger.warning(
                "East Money returned invalid JSON for keyword=%s page=%s",
                keyword, page,
            )
            return []

        items = data.get("result", {}).get("cmsArticleWebOld") or []
        records: list[dict[str, Any]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            title = (item.get("title") or "").replace("<em>", "").replace("</em>", "")
            content = (item.get("content") or "").replace("<em>", "").replace("</em>", "")
            code = item.get("code") or ""
            records.append({
                "title": title,
                "content": content,
                "published_at": item.get("date"),
                "source": SOURCE_EASTMONEY,
                "url": f"http://finance.eastmoney.com/a/{code}.html" if code else "",
            })

        _normalize_datetime(records)
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

        try:
            raw = await with_retry(
                lambda: loop.run_in_executor(None, _sync),
                source_name="news_cls",
            )
        except (asyncio.CancelledError, DataSourceError):
            return []

        records = _rename_columns(raw, CLS_COLUMNS)
        for r in records:
            r["source"] = SOURCE_CLS
        _normalize_datetime(records)
        return records

    async def fetch_wallstreetcn(self) -> list[dict[str, Any]]:
        """Fetch from WallStreetCN live feed (华尔街见闻 7×24 快讯).

        Calls the api-one.wallstcn.com live content endpoint.  Returns
        up to 50 recent flash/live items with title, content, and URL.
        """
        all_records: list[dict[str, Any]] = []
        cursor: int | None = None

        async with httpx.AsyncClient(timeout=15.0) as client:
            for _ in range(3):  # fetch up to 3 pages
                params: dict[str, Any] = {
                    "channel": "global-channel",
                    "client": "pc",
                    "limit": 50,
                    "first_page": cursor is None,
                }
                if cursor is not None:
                    params["cursor"] = cursor

                try:
                    resp = await client.get(
                        "https://api-one.wallstcn.com/apiv1/content/lives",
                        params=params,
                        headers={
                            "User-Agent": (
                                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                                "AppleWebKit/537.36"
                            ),
                            "Accept": "application/json",
                        },
                    )
                    resp.raise_for_status()
                    body = resp.json()
                except Exception as exc:
                    logger.error("WallStreetCN API failed: %s", exc)
                    break

                data = body.get("data") or {}
                items = data.get("items") or []
                if not items:
                    break

                for item in items:
                    if not isinstance(item, dict):
                        continue
                    title = item.get("title") or ""
                    content = item.get("content_text") or item.get("content") or ""
                    if not title and not content:
                        continue
                    display_time = item.get("display_time")
                    published_at = (
                        datetime.fromtimestamp(display_time)
                        if isinstance(display_time, (int, float))
                        else None
                    )
                    all_records.append({
                        "title": title,
                        "content": content,
                        "published_at": published_at,
                        "source": SOURCE_WALLSTREETCN,
                        "url": (
                            item.get("uri")
                            or f"https://wallstreetcn.com/livenews/{item.get('id') or ''}"
                        ),
                    })

                next_cursor = data.get("next_cursor")
                if next_cursor:
                    cursor = next_cursor
                else:
                    break

        logger.info("WallStreetCN: %d articles", len(all_records))
        return all_records
