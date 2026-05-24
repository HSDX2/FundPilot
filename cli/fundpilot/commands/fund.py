"""Fund commands — search, detail, nav, estimate."""

from __future__ import annotations

from typing import Annotated

import typer

from fundpilot.client import APIClient
from fundpilot.output import format_result

fund_app = typer.Typer(help="基金查询与估值")


@fund_app.command("search")
def fund_search(
    name: Annotated[
        str | None, typer.Option("--name", "-n", help="基金名称模糊搜索")
    ] = None,
    type: Annotated[
        str | None,
        typer.Option(
            "--type", "-t",
            help="基金类型: stock/mixed/index/etf/bond/monetary/qdii",
        ),
    ] = None,
    company: Annotated[
        str | None, typer.Option("--company", "-c", help="基金公司名称")
    ] = None,
    page: Annotated[int, typer.Option("--page", "-p", help="页码")] = 1,
    page_size: Annotated[
        int, typer.Option("--page-size", "-s", help="每页数量")
    ] = 20,
    table: Annotated[
        bool, typer.Option("--table", help="以表格形式输出")
    ] = False,
) -> None:
    """搜索基金列表."""
    client = APIClient()
    params = {"page": page, "page_size": page_size}
    if name:
        params["name"] = name
    if type:
        params["type"] = type
    if company:
        params["company"] = company
    result = client.get("/funds", params)
    format_result(result, table=table)


@fund_app.command("detail")
def fund_detail(
    code: Annotated[str, typer.Argument(help="基金代码，如 000001")],
) -> None:
    """查询基金详情."""
    client = APIClient()
    result = client.get(f"/funds/{code}")
    format_result(result)


@fund_app.command("nav")
def fund_nav(
    code: Annotated[str, typer.Argument(help="基金代码，如 000001")],
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
    """查询基金净值历史."""
    client = APIClient()
    params: dict = {}
    if start:
        params["start_date"] = start
    if end:
        params["end_date"] = end
    result = client.get(f"/funds/{code}/nav", params)
    format_result(result, table=table)


@fund_app.command("estimate")
def fund_estimate(
    code: Annotated[str, typer.Argument(help="基金代码，如 000001")],
) -> None:
    """查询基金最新盘中估值."""
    client = APIClient()
    result = client.get(f"/funds/{code}/estimate")
    format_result(result)


@fund_app.command("batch-estimate")
def fund_batch_estimate(
    codes: Annotated[
        str,
        typer.Argument(help="基金代码列表，逗号分隔，如 000001,000011"),
    ],
) -> None:
    """批量查询基金估值."""
    client = APIClient()
    result = client.get("/funds/estimates/batch", {"codes": codes})
    format_result(result)
