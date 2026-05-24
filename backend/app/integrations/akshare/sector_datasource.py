"""AkShare-based sector/board data source."""

import asyncio
import logging
from typing import Any

import akshare as ak

from app.integrations.base import with_retry

logger = logging.getLogger(__name__)

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
    """Sector/board data from AkShare."""

    @property
    def name(self) -> str:
        return "akshare_sector"

    async def fetch_industry_list(self) -> list[dict[str, Any]]:
        """Fetch SW industry board list."""
        loop = asyncio.get_running_loop()

        def _sync() -> list[dict[str, Any]]:
            df = ak.stock_board_industry_spot_em()
            return df.to_dict(orient="records")

        raw = await with_retry(
            lambda: loop.run_in_executor(None, _sync),
            source_name=self.name,
        )
        return _rename_columns(raw, BOARD_LIST_COLUMNS)

    async def fetch_concept_list(self) -> list[dict[str, Any]]:
        """Fetch concept board list."""
        loop = asyncio.get_running_loop()

        def _sync() -> list[dict[str, Any]]:
            df = ak.stock_board_concept_spot_em()
            return df.to_dict(orient="records")

        raw = await with_retry(
            lambda: loop.run_in_executor(None, _sync),
            source_name=self.name,
        )
        return _rename_columns(raw, BOARD_LIST_COLUMNS)

    async def fetch_board_history(
        self,
        symbol: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch historical daily data for a board."""
        loop = asyncio.get_running_loop()

        def _sync() -> list[dict[str, Any]]:
            df = ak.stock_board_industry_hist_em(
                symbol=symbol,
                start_date=start_date or "19700101",
                end_date=end_date or "21000101",
            )
            return df.to_dict(orient="records")

        raw = await with_retry(
            lambda: loop.run_in_executor(None, _sync),
            source_name=self.name,
        )
        return _rename_columns(raw, BOARD_HISTORY_COLUMNS)

    async def fetch_board_realtime(self) -> list[dict[str, Any]]:
        """Fetch real-time data for all industry boards."""
        return await self.fetch_industry_list()

    async def fetch_board_realtime_by_category(
        self, category: str
    ) -> list[dict[str, Any]]:
        """Fetch real-time board data by category (industry / concept)."""
        if category == "industry":
            return await self.fetch_industry_list()
        elif category == "concept":
            return await self.fetch_concept_list()
        return []

    async def fetch_sector_fund_flow(
        self,
        indicator: str = "今日",
        sector_type: str = "行业资金流",
    ) -> list[dict[str, Any]]:
        """Fetch sector fund flow ranking data.

        Args:
            indicator: "今日", "5日", or "10日"
            sector_type: "行业资金流", "概念资金流", or "地域资金流"
        """
        loop = asyncio.get_running_loop()

        def _sync() -> list[dict[str, Any]]:
            df = ak.stock_sector_fund_flow_rank(
                indicator=indicator, sector_type=sector_type,
            )
            return df.to_dict(orient="records")

        raw = await with_retry(
            lambda: loop.run_in_executor(None, _sync),
            source_name=self.name,
        )
        mapped = []
        for row in raw:
            mapped.append({
                "name": row.get("名称"),
                "change_pct": row.get("今日涨跌幅"),
                "main_force_net_inflow": row.get("今日主力净流入-净额"),
                "main_force_net_inflow_ratio": row.get("今日主力净流入-净占比"),
                "super_large_net_inflow": row.get("今日超大单净流入-净额"),
                "large_net_inflow": row.get("今日大单净流入-净额"),
                "middle_net_inflow": row.get("今日中单净流入-净额"),
                "small_net_inflow": row.get("今日小单净流入-净额"),
            })
        return mapped

    async def fetch_board_cons(
        self,
        symbol: str,
    ) -> list[dict[str, Any]]:
        """Fetch constituent stocks of a board."""
        loop = asyncio.get_running_loop()

        def _sync() -> list[dict[str, Any]]:
            df = ak.stock_board_industry_cons_em(symbol=symbol)
            return df.to_dict(orient="records")

        raw = await with_retry(
            lambda: loop.run_in_executor(None, _sync),
            source_name=self.name,
        )
        return _rename_columns(raw, BOARD_CONS_COLUMNS)
