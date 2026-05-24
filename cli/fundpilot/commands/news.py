"""News commands — search, detail."""

from __future__ import annotations

from typing import Annotated

import typer

from fundpilot.client import APIClient
from fundpilot.output import format_result

news_app = typer.Typer(help="新闻查询")


@news_app.command("search")
def news_search(
    keyword: Annotated[
        str | None, typer.Option("--keyword", "-k", help="关键词搜索")
    ] = None,
    source: Annotated[
        str | None, typer.Option("--source", "-s", help="来源筛选")
    ] = None,
    start: Annotated[
        str | None, typer.Option("--start", help="开始时间 ISO 格式")
    ] = None,
    end: Annotated[
        str | None, typer.Option("--end", help="结束时间 ISO 格式")
    ] = None,
    page: Annotated[int, typer.Option("--page", "-p", help="页码")] = 1,
    page_size: Annotated[
        int, typer.Option("--page-size", help="每页数量")
    ] = 20,
    table: Annotated[
        bool, typer.Option("--table", help="以表格形式输出")
    ] = False,
) -> None:
    """搜索新闻列表."""
    client = APIClient()
    params: dict = {"page": page, "page_size": page_size}
    if keyword:
        params["keyword"] = keyword
    if source:
        params["source"] = source
    if start:
        params["start"] = start
    if end:
        params["end"] = end
    result = client.get("/news", params)
    format_result(result, table=table)


@news_app.command("detail")
def news_detail(
    news_id: Annotated[str, typer.Argument(help="新闻 UUID")],
) -> None:
    """查询新闻详情."""
    client = APIClient()
    result = client.get(f"/news/{news_id}")
    format_result(result)
