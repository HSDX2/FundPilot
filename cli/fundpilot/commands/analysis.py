"""Analysis commands — reports, advice, sentiment."""

from __future__ import annotations

from typing import Annotated

import typer

from fundpilot.client import APIClient
from fundpilot.output import format_result

analysis_app = typer.Typer(help="AI 分析报告与建议")


@analysis_app.command("report-list")
def report_list(
    report_type: Annotated[
        str,
        typer.Option("--type", "-t", help="报告类型: daily/weekly/monthly"),
    ] = "daily",
    page: Annotated[int, typer.Option("--page", "-p", help="页码")] = 1,
    page_size: Annotated[
        int, typer.Option("--page-size", "-s", help="每页数量")
    ] = 20,
) -> None:
    """查询分析报告列表."""
    client = APIClient()
    result = client.get(
        "/analysis/reports",
        {"report_type": report_type, "page": page, "page_size": page_size},
    )
    format_result(result)


@analysis_app.command("report-latest")
def report_latest(
    report_type: Annotated[
        str,
        typer.Option("--type", "-t", help="报告类型: daily/weekly/monthly"),
    ] = "daily",
) -> None:
    """查询最新分析报告."""
    client = APIClient()
    result = client.get("/analysis/reports/latest", {"report_type": report_type})
    format_result(result)


@analysis_app.command("advice-list")
def advice_list(
    action: Annotated[
        str | None,
        typer.Option("--action", "-a", help="筛选: buy/hold/reduce/redeem"),
    ] = None,
    page: Annotated[int, typer.Option("--page", "-p", help="页码")] = 1,
    page_size: Annotated[
        int, typer.Option("--page-size", "-s", help="每页数量")
    ] = 20,
) -> None:
    """查询基金操作建议列表."""
    client = APIClient()
    params: dict = {"page": page, "page_size": page_size}
    if action:
        params["action"] = action
    result = client.get("/analysis/advice", params)
    format_result(result)


@analysis_app.command("sentiment-latest")
def sentiment_latest() -> None:
    """查询最新市场情绪综合评分."""
    client = APIClient()
    result = client.get("/analysis/sentiment/latest")
    format_result(result)
