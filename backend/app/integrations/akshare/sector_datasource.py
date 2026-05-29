"""AkShare-based sector/board data source.

East Money's push2*.eastmoney.com API is partially blocked by CDN/WAF.

Reachable:
  - push2his.eastmoney.com/api/qt/stock/fflow/daykline/get (IPv4 only)
  - data.eastmoney.com (page scraping for board codes)

Blocked (all IPv4/v6):
  - push2.eastmoney.com/api/qt/clist/get (board code listing)

We scrape data.eastmoney.com for EM board codes and use push2his (IPv4)
for fund flow history.  THS (10jqka.com.cn) remains the fallback.
"""

import asyncio
import logging
import re
import socket
from datetime import date
from typing import Any

import akshare as ak

from app.integrations.base import DataSourceError, with_retry

logger = logging.getLogger(__name__)

# ── IPv4 workaround for push2his ──
# East Money's CDN/WAF blocks IPv6 connections to push2his.eastmoney.com
# but IPv4 works. We monkey-patch socket to force IPv4 for this host.

_em_ipv4_patched = False


def _patch_push2his_ipv4() -> None:
    """Force IPv4 DNS resolution for push2his.eastmoney.com (IPv6 blocked by WAF)."""
    global _em_ipv4_patched
    if _em_ipv4_patched:
        return

    orig_getaddrinfo = socket.getaddrinfo

    def _patched_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
        if "push2his.eastmoney.com" in host:
            family = socket.AF_INET
        return orig_getaddrinfo(host, port, family, type, proto, flags)

    socket.getaddrinfo = _patched_getaddrinfo
    _em_ipv4_patched = True


# ── East-Money-era column mappings (kept for fetch_board_history / _cons) ──

BOARD_LIST_COLUMNS: dict[str, str] = {
    "板块名称": "name",
    "板块代码": "code",
    "涨跌幅": "change_pct",
    "涨跌额": "change_amount",
    "总市值": "total_market_cap",
    "换手率": "turnover_rate",
}

BOARD_HISTORY_COLUMNS: dict[str, str] = {
    "date": "date",
    "开盘": "open",
    "收盘": "close",
    "最高": "high",
    "最低": "low",
    "成交量": "volume",
    "成交额": "turnover",
    "振幅": "amplitude",
    "涨跌幅": "change_pct",
    "涨跌额": "change_amount",
    "换手率": "turnover_rate",
}

BOARD_CONS_COLUMNS: dict[str, str] = {
    "代码": "stock_code",
    "名称": "stock_name",
    "现价": "price",
    "涨跌幅": "change_pct",
}


# ── THS column mappings ──

THS_INDUSTRY_SUMMARY_COLUMNS: dict[str, str] = {
    "板块": "name",
    "涨跌幅": "change_pct",
    "总成交量": "volume",
    "总成交额": "turnover",
    "净流入": "net_inflow",
    "上涨家数": "up_count",
    "下跌家数": "down_count",
    "均价": "price",
    "领涨股": "leader_name",
    "领涨股-最新价": "leader_price",
    "领涨股-涨跌幅": "leader_pct",
}


def _parse_amount(value: object) -> float | None:
    """Parse a THS amount string like ``"1.23亿"`` or ``"-1234.56万"`` to float (yuan)."""
    if value is None:
        return None
    s = str(value).replace(",", "").strip()
    if not s:
        return None
    if s.endswith("亿"):
        return float(s[:-1]) * 1e8
    if s.endswith("万"):
        return float(s[:-1]) * 1e4
    try:
        return float(s)
    except ValueError:
        return None


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


class SectorDataSource:
    """Sector/board data from AkShare (East Money + THS fallback)."""

    @property
    def name(self) -> str:
        return "akshare_sector"

    # ── Industry list ──

    async def fetch_industry_list(self) -> list[dict[str, Any]]:
        """Fetch SW industry board list (THS source — East Money push2 blocked)."""
        loop = asyncio.get_running_loop()

        def _sync() -> list[dict[str, Any]]:
            # 1. Get industry names + THS codes
            names_df = ak.stock_board_industry_name_ths()  # → name, code

            # 2. Get real-time summary stats
            stats_df = ak.stock_board_industry_summary_ths()  # → 板块, 涨跌幅, …

            if names_df.empty and stats_df.empty:
                return []

            # 3. Merge on name ("name" vs "板块")
            if stats_df.empty:
                merged = names_df
                merged["涨跌幅"] = None
                merged["均价"] = None
                merged["总成交量"] = None
                merged["总成交额"] = None
                merged["净流入"] = None
                merged["上涨家数"] = None
                merged["下跌家数"] = None
            elif names_df.empty:
                merged = stats_df.rename(columns={"板块": "name"})
                merged["code"] = None
            else:
                merged = stats_df.merge(
                    names_df,
                    left_on="板块",
                    right_on="name",
                    how="left",
                )
            result = []
            for _, row in merged.iterrows():
                result.append({
                    "name": row.get("name"),
                    "code": row.get("code"),
                    "change_pct": row.get("涨跌幅"),
                    "price": row.get("均价"),
                    "volume": row.get("总成交量"),
                    "turnover": row.get("总成交额"),
                    "net_inflow": row.get("净流入"),
                    "up_count": row.get("上涨家数"),
                    "down_count": row.get("下跌家数"),
                })
            return result

        return await with_retry(
            lambda: loop.run_in_executor(None, _sync),
            source_name=self.name,
        )

    # ── Concept list ──

    async def fetch_concept_list(self) -> list[dict[str, Any]]:
        """获取概念板块列表（含最新价和涨跌幅）。

        先获取名称和代码，再并发拉取每个板块的近两日指数数据以计算涨跌幅。
        """
        loop = asyncio.get_running_loop()

        def _get_names() -> list[dict[str, Any]]:
            df = ak.stock_board_concept_name_ths()
            result = []
            for _, row in df.iterrows():
                result.append({
                    "name": row.get("name"),
                    "code": row.get("code"),
                })
            return result

        concepts = await with_retry(
            lambda: loop.run_in_executor(None, _get_names),
            source_name=self.name,
        )

        if not concepts:
            return []

        # 并发获取每个概念板块的近两日指数行情
        sem = asyncio.Semaphore(8)

        async def _fetch_one(concept: dict) -> dict:
            async with sem:

                def _sync():
                    try:
                        df = ak.stock_board_concept_index_ths(
                            symbol=concept["name"],
                            start_date="20200101",
                            end_date="21000101",
                        )
                        if df is None or df.empty:
                            return None
                        return df.tail(2)
                    except Exception:
                        logger.debug(
                            "Failed to fetch index for concept %s",
                            concept["name"],
                        )
                        return None

                tail = await loop.run_in_executor(None, _sync)
                if tail is not None and len(tail) >= 2:
                    latest = tail.iloc[-1]
                    prev = tail.iloc[-2]
                    close = latest.get("收盘价")
                    prev_close = prev.get("收盘价")
                    concept["price"] = close
                    if close and prev_close and prev_close != 0:
                        concept["change_pct"] = round(
                            float((close - prev_close) / prev_close * 100), 2,
                        )
                    else:
                        concept["change_pct"] = None
                    concept["volume"] = latest.get("成交量")
                    concept["turnover"] = latest.get("成交额")
                elif tail is not None and len(tail) == 1:
                    row = tail.iloc[0]
                    concept["price"] = row.get("收盘价")
                    concept["change_pct"] = None
                    concept["volume"] = row.get("成交量")
                    concept["turnover"] = row.get("成交额")
                return concept

        return list(await asyncio.gather(*(_fetch_one(c) for c in concepts)))

    # ── Board history (THS source — push2 kline now also blocked) ──

    async def fetch_board_history(
        self,
        name: str,
        category: str = "industry",
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch historical daily data for a board by sector *name*.

        Args:
            name: Sector display name, e.g. "半导体" or "AI应用".
            category: "industry" or "concept".
            start_date: Start date in ISO format (YYYY-MM-DD) or YYYYMMDD.
            end_date: End date in ISO format (YYYY-MM-DD) or YYYYMMDD.
        """
        # AkShare THS APIs expect YYYYMMDD format — strip dashes if ISO format
        def _fmt(d: str | None) -> str:
            if d is None:
                return ""
            return d.replace("-", "")

        loop = asyncio.get_running_loop()

        def _sync() -> list[dict[str, Any]]:
            s = _fmt(start_date) or "19700101"
            e = _fmt(end_date) or "21000101"
            if category == "concept":
                df = ak.stock_board_concept_index_ths(
                    symbol=name,
                    start_date=s,
                    end_date=e,
                )
            else:
                df = ak.stock_board_industry_index_ths(
                    symbol=name,
                    start_date=s,
                    end_date=e,
                )
            return df.to_dict(orient="records")

        raw = await with_retry(
            lambda: loop.run_in_executor(None, _sync),
            source_name=self.name,
        )
        # THS column names differ from East Money:
        # 日期→date, 开盘价→open, 收盘价→close, 最高价→high, 最低价→low,
        # 成交量→volume, 成交额→turnover
        mapped = []
        for row in raw:
            raw_date = row.get("日期")
            if raw_date is None:
                continue
            mapped.append({
                "date": raw_date,
                "open": row.get("开盘价"),
                "close": row.get("收盘价"),
                "high": row.get("最高价"),
                "low": row.get("最低价"),
                "volume": row.get("成交量"),
                "turnover": row.get("成交额"),
            })
        return mapped

    # ── Realtime ──

    async def fetch_board_realtime(self) -> list[dict[str, Any]]:
        """Fetch real-time data for all boards (industry + concept)."""
        industry = await self.fetch_industry_list()
        concept = await self.fetch_concept_list()
        return industry + concept

    async def fetch_board_realtime_by_category(
        self, category: str
    ) -> list[dict[str, Any]]:
        """Fetch real-time board data by category (industry / concept)."""
        if category == "industry":
            return await self.fetch_industry_list()
        elif category == "concept":
            return await self.fetch_concept_list()
        return []

    # ── Realtime sector quote ──

    async def fetch_sector_realtime(
        self, name: str, category: str = "industry",
    ) -> dict[str, Any] | None:
        """获取单个板块实时行情（涨跌幅、成交量、成交额）。

        行业板块通过 THS summary API 批量获取后按名称筛选。
        概念板块无批量实时 API，改用 stock_board_concept_index_ths 逐只查询。
        Returns: {price, change_pct, volume, turnover} 或 None。
        """
        loop = asyncio.get_running_loop()

        if category == "concept":
            def _sync_single() -> dict[str, Any] | None:
                df = ak.stock_board_concept_index_ths(symbol=name)
                if df is None or df.empty:
                    return None
                last = df.iloc[-1]
                return {
                    "name": name,
                    "price": last.get("收盘价"),
                    "change_pct": None,  # 需前后对比计算，接口不直接提供
                    "volume": last.get("成交量"),
                    "turnover": last.get("成交额"),
                }

            return await with_retry(
                lambda: loop.run_in_executor(None, _sync_single),
                source_name=f"{self.name}(realtime_concept)",
            )

        # 行业板块：批量获取
        def _sync_industry() -> list[dict[str, Any]]:
            df = ak.stock_board_industry_summary_ths()
            if df is None or df.empty:
                return []
            result = []
            for _, row in df.iterrows():
                result.append({
                    "name": row.get("板块"),
                    "price": row.get("均价"),
                    "change_pct": row.get("涨跌幅"),
                    "volume": row.get("总成交量"),
                    "turnover": row.get("总成交额"),
                })
            return result

        rows = await with_retry(
            lambda: loop.run_in_executor(None, _sync_industry),
            source_name=f"{self.name}(realtime_industry)",
        )
        for r in rows:
            if r["name"] == name:
                return r
        # 模糊匹配
        import difflib
        names = [r["name"] for r in rows]
        close = difflib.get_close_matches(name, names, n=1, cutoff=0.7)
        if close:
            return next(r for r in rows if r["name"] == close[0])
        return None

    # ── Sector fund flow (THS source — East Money push2 blocked) ──

    async def fetch_sector_fund_flow(
        self,
        indicator: str = "今日",
        sector_type: str = "行业资金流",
    ) -> list[dict[str, Any]]:
        """Fetch sector fund flow ranking data via THS (同花顺).

        THS provides total net flow (净额) without 主力/中单/散户 breakdown.
        The total is stored in ``main_force_net_inflow``; middle/retail are None.
        """
        indicator_map = {"今日": "即时", "3日": "3日排行", "5日": "5日排行", "10日": "10日排行"}
        ths_indicator = indicator_map.get(indicator, "即时")

        loop = asyncio.get_running_loop()

        def _sync() -> list[dict[str, Any]]:
            try:
                if sector_type == "概念资金流":
                    df = ak.stock_fund_flow_concept(ths_indicator)
                else:
                    df = ak.stock_fund_flow_industry(ths_indicator)
            except (AttributeError, ValueError, TypeError) as exc:
                logger.warning(
                    "%s %s failed: %s", sector_type, ths_indicator, exc,
                )
                return []

            if df is None or df.empty:
                return []

            result = []
            for _, row in df.iterrows():
                net_inflow = _parse_amount(row.get("净额"))
                # THS 数据单位为亿，需转为元
                if net_inflow is not None:
                    net_inflow = net_inflow * 1e8
                result.append({
                    "name": row.get("行业"),
                    "main_force_net_inflow": net_inflow,
                    "middle_net_inflow": None,
                    "small_net_inflow": None,
                })
            return result

        return await with_retry(
            lambda: loop.run_in_executor(None, _sync),
            source_name=self.name,
        )

    # ── Sector fund flow history (push2his — different domain, not blocked) ──

    # 东方财富板块代码缓存（按需加载一次）
    _em_code_map: dict[str, str] | None = None
    _em_load_failed: bool = False

    @classmethod
    def _load_em_sector_codes(cls) -> dict[str, str]:
        """加载东方财富全部板块的名称→代码映射（多层回退）。

        1. 爬取 data.eastmoney.com/bkzj/hy.html 页面（快速，单请求）
        2. 若失败，走 AkShare stock_board_concept/industry_name_em
        3. 最后回退到 AkShare 内部 _get_stock_sector_fund_flow_summary_code
        """
        if cls._em_code_map is not None:
            return cls._em_code_map
        if cls._em_load_failed:
            return {}

        import requests as req

        mapping: dict[str, str] = {}

        # 策略 1：爬取板块资金流向页面（不依赖 push2 API）
        try:
            r = req.get(
                "https://data.eastmoney.com/bkzj/hy.html",
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
                    ),
                },
                timeout=15,
            )
            r.raise_for_status()
            for m in re.finditer(
                r'href="/bkzj/(BK\d{4})\.html"[^>]*>([^<]+)<', r.text,
            ):
                name = m.group(2).strip()
                if name and len(name) <= 30:
                    mapping[name] = m.group(1)
        except Exception:
            logger.debug("EM page scraping failed, trying next strategy")

        # 策略 2：通过 AkShare 的封装函数
        if len(mapping) < 50:
            try:
                df = ak.stock_board_concept_name_em()
                for _, row in df.iterrows():
                    name = row.get("板块名称")
                    code = row.get("板块代码")
                    if name and code:
                        mapping[name] = str(code)
            except Exception:
                logger.debug("stock_board_concept_name_em failed, trying next")

            try:
                df = ak.stock_board_industry_name_em()
                for _, row in df.iterrows():
                    name = row.get("板块名称")
                    code = row.get("板块代码")
                    if name and code:
                        mapping[name] = str(code)
            except Exception:
                logger.debug("stock_board_industry_name_em failed")

        # 策略 3：回退到 AkShare 内部映射
        if len(mapping) < 10:
            try:
                from akshare.stock.stock_fund_em import (
                    _get_stock_sector_fund_flow_summary_code,
                )
                mapping.update(_get_stock_sector_fund_flow_summary_code())
            except Exception:
                logger.warning("All EM sector code strategies failed")

        cls._em_code_map = mapping if mapping else None
        if not mapping:
            cls._em_load_failed = True
            logger.warning("All EM sector code strategies failed")
        else:
            logger.info(
                "Loaded %d East Money sector codes", len(mapping),
            )
        return mapping

    async def fetch_sector_fund_flow_range(
        self,
        symbol: str,
        start_date: date,
    ) -> list[dict[str, Any]]:
        """获取单个板块历史资金流向。

        优先：东方财富 push2his API（需 IPv4，IPv6 被 WAF 阻断）。
        若 push2his 失败，回退到 THS 今日资金流排行（仅当天数据，无主力/中单/散户细分）。
        """
        loop = asyncio.get_running_loop()

        # 解析 EM 板块代码（从缓存的映射或实时加载）
        em_code = self._resolve_em_code(symbol)
        if em_code is not None:
            # EM 代码可用，强制 IPv4 后尝试 push2his API
            _patch_push2his_ipv4()

            def _sync(secid: str) -> list[dict[str, Any]]:
                import requests as req

                url = "https://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get"
                params = {
                    "lmt": "0",
                    "klt": "101",
                    "fields1": "f1,f2,f3,f7",
                    "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64,f65",
                    "secid": secid,
                }
                r = req.get(url, params=params, timeout=30)
                r.raise_for_status()
                data_json = r.json()
                return data_json.get("data", {}).get("klines") or []

            try:
                klines = await with_retry(
                    lambda: loop.run_in_executor(None, _sync, f"90.{em_code}"),
                    source_name=f"{self.name}(EM)",
                    max_retries=2,
                    base_delay=1.0,
                )
            except DataSourceError:
                logger.warning(
                    "EM push2his failed for '%s', falling back to THS today's data",
                    symbol,
                )
                return await self._fetch_thz_fund_flow_today(symbol)

            # 解析 klines（push2his 数据单位为元，直接使用）
            result = []
            today = date.today()
            for line in klines:
                parts = line.split(",") if isinstance(line, str) else line
                if not parts or len(parts) < 6:
                    continue
                row_date_str = str(parts[0])
                if row_date_str.startswith("="):
                    row_date_str = row_date_str[1:]
                try:
                    row_date = date.fromisoformat(row_date_str)
                except (ValueError, TypeError):
                    continue
                if row_date < start_date:
                    continue
                try:
                    main_val = float(parts[1])
                    small_val = float(parts[2])
                    middle_val = float(parts[3])
                except (ValueError, TypeError):
                    continue
                result.append({
                    "date": row_date,
                    "name": symbol,
                    "main_force_net_inflow": main_val,
                    "small_net_inflow": small_val,
                    "middle_net_inflow": middle_val,
                })

            # push2his 可能不含今天数据（交易日未结束），补充 THS 今日数据
            if not any(r.get("date") == today for r in result):
                try:
                    today_data = await self._fetch_thz_fund_flow_today(symbol)
                    if today_data:
                        result.extend(today_data)
                except Exception:
                    logger.debug("Failed to fetch THS today data for '%s'", symbol)
            return result

        # EM 代码不可用，回退到 THS 今日数据
        return await self._fetch_thz_fund_flow_today(symbol)

    async def _load_em_codes_background(self) -> None:
        """后台加载 EM 板块代码映射，不影响当前请求。"""
        try:
            await asyncio.get_running_loop().run_in_executor(
                None, self._load_em_sector_codes,
            )
            logger.info("Background EM code loading completed")
        except Exception:
            logger.debug("Background EM code loading failed")

    def _resolve_em_code(self, symbol: str) -> str | None:
        """加载 EM 板块代码，返回 symbol 对应的 EM 板块代码，失败返回 None。"""
        import difflib

        code_map = self._load_em_sector_codes()
        em_code = code_map.get(symbol)
        if em_code is None and code_map:
            close = difflib.get_close_matches(symbol, code_map.keys(), n=1, cutoff=0.8)
            if close:
                em_code = code_map[close[0]]
                logger.debug(
                    "Fuzzy matched '%s' → EM '%s' (%s)", symbol, close[0], em_code,
                )
        return em_code

    async def _fetch_thz_fund_flow_today(
        self, symbol: str,
    ) -> list[dict[str, Any]]:
        """THS 今日资金流排行中查找指定板块的净流入数据（无主力/中单/散户细分）。"""
        import difflib

        loop = asyncio.get_running_loop()
        today = date.today()

        # 判断板块类型：先查行业，再查概念
        for sector_type, ak_func in [
            ("行业资金流", ak.stock_fund_flow_industry),
            ("概念资金流", ak.stock_fund_flow_concept),
        ]:
            try:

                def _fetch(akf=ak_func) -> list[dict[str, Any]]:
                    df = akf("即时")
                    if df is None or df.empty:
                        return []
                    result = []
                    # THS 行业和概念资金流都使用「行业」列名
                    for _, row in df.iterrows():
                        raw_name = row.get("行业", "")
                        raw_net = row.get("净额", "0")
                        net = _parse_amount(str(raw_net))
                        if net is not None:
                            net = net * 1e8  # THS 亿 → 元
                        result.append({
                            "name": str(raw_name).strip(),
                            "net_inflow": net,
                        })
                    return result

                ranking = await loop.run_in_executor(None, _fetch)
                # 精确查找
                found = next((r for r in ranking if r["name"] == symbol), None)
                # 模糊查找
                if found is None and ranking:
                    names = [r["name"] for r in ranking]
                    close = difflib.get_close_matches(symbol, names, n=1, cutoff=0.7)
                    if close:
                        found = next(r for r in ranking if r["name"] == close[0])
                if found and found["net_inflow"] is not None:
                    return [{
                        "date": today,
                        "name": symbol,
                        "main_force_net_inflow": found["net_inflow"],
                        "small_net_inflow": None,
                        "middle_net_inflow": None,
                    }]
            except Exception:
                logger.debug(
                    "THS %s fund flow ranking failed for '%s', trying next",
                    sector_type, symbol,
                )
        return []

    # ── Board constituents (broken — push2 clist/get blocked) ──

    async def fetch_board_cons(
        self,
        symbol: str,
    ) -> list[dict[str, Any]]:
        """Fetch constituent stocks of a board.

        East Money's push2 endpoint is blocked.  Raises DataSourceError until a
        THS alternative or proxy workaround becomes available.
        """
        raise DataSourceError(
            self.name,
            RuntimeError(
                "push2.eastmoney.com API blocked by CDN/WAF — "
                "no THS alternative available for board constituents"
            ),
        )
