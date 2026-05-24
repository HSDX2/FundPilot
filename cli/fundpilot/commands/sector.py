"""Sector commands — search, rank, money-flow."""

from __future__ import annotations

from typing import Annotated

import typer

from fundpilot.client import APIClient
from fundpilot.output import format_result

sector_app = typer.Typer(help="板块查询与排行")


@sector_app.command("search")
def sector_search(
    name: Annotated[
        str | None, typer.Option("--name", "-n", help="板块名称模糊搜索")
    ] = None,
    category: Annotated[
        str | None,
        typer.Option("--category", "-c", help="板块分类: industry/concept"),
    ] = None,
    page: Annotated[int, typer.Option("--page", "-p", help="页码")] = 1,
    page_size: Annotated[
        int, typer.Option("--page-size", "-s", help="每页数量")
    ] = 20,
    table: Annotated[
        bool, typer.Option("--table", help="以表格形式输出")
    ] = False,
) -> None:
    """搜索板块列表."""
    client = APIClient()
    params: dict = {"page": page, "page_size": page_size}
    if name:
        params["name"] = name
    if category:
        params["category"] = category
    result = client.get("/sectors", params)
    format_result(result, table=table)


@sector_app.command("rank")
def sector_rank(
    category: Annotated[
        str | None,
        typer.Option("--category", "-c", help="板块分类: industry/concept"),
    ] = None,
    limit: Annotated[
        int, typer.Option("--limit", "-n", help="返回条数")
    ] = 20,
    table: Annotated[
        bool, typer.Option("--table", help="以表格形式输出")
    ] = True,
) -> None:
    """查询板块涨跌排行."""
    client = APIClient()
    params: dict = {"limit": limit}
    if category:
        params["category"] = category
    result = client.get("/sectors/rank/current", params)
    format_result(result, table=table)


@sector_app.command("money-flow")
def sector_money_flow(
    sector_id: Annotated[str, typer.Argument(help="板块 UUID")],
    start: Annotated[
        str | None, typer.Option("--start", help="开始日期 YYYY-MM-DD")
    ] = None,
    end: Annotated[
        str | None, typer.Option("--end", help="结束日期 YYYY-MM-DD")
    ] = None,
    table: Annotated[
        bool, typer.Option("--table", help="以表格形式输出")
    ] = False,
) -> None:
    """查询板块资金流向历史."""
    client = APIClient()
    params: dict = {}
    if start:
        params["start_date"] = start
    if end:
        params["end_date"] = end
    result = client.get(f"/sectors/{sector_id}/money-flow", params)
    format_result(result, table=table)
