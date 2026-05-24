"""Collect commands — trigger, status, stop, logs, settings."""

from __future__ import annotations

from typing import Annotated

import typer

from fundpilot.client import APIClient
from fundpilot.output import format_result

collect_app = typer.Typer(help="采集控制与监控")


@collect_app.command("trigger")
def collect_trigger(
    name: Annotated[str, typer.Argument(help="采集器名称")],
    sources: Annotated[
        str | None,
        typer.Option(
            "--sources",
            help="新闻源列表，逗号分隔 (仅 news 采集器生效)",
        ),
    ] = None,
) -> None:
    """手动触发数据采集."""
    client = APIClient()
    body: dict = {"collector": name}
    if sources:
        body["sources"] = [s.strip() for s in sources.split(",") if s.strip()]
    result = client.post("/collect/trigger", body)
    format_result(result)


@collect_app.command("status")
def collect_status(
    name: Annotated[
        str | None,
        typer.Argument(help="采集器名称，不指定则显示全部"),
    ] = None,
) -> None:
    """查询采集任务状态."""
    client = APIClient()
    if name:
        result = client.get(f"/collect/status/{name}")
    else:
        result = client.get("/collect/status")
    format_result(result)


@collect_app.command("stop")
def collect_stop(
    name: Annotated[str, typer.Argument(help="采集器名称")],
) -> None:
    """强制停止采集任务."""
    client = APIClient()
    result = client.post(f"/collect/stop/{name}")
    format_result(result)


@collect_app.command("logs")
def collect_logs(
    collector: Annotated[
        str | None,
        typer.Option("--collector", "-c", help="采集器名称筛选"),
    ] = None,
    page: Annotated[int, typer.Option("--page", "-p", help="页码")] = 1,
    page_size: Annotated[
        int, typer.Option("--page-size", "-s", help="每页数量")
    ] = 20,
    table: Annotated[
        bool, typer.Option("--table", help="以表格形式输出")
    ] = True,
) -> None:
    """查询采集执行日志."""
    client = APIClient()
    params: dict = {"page": page, "page_size": page_size}
    if collector:
        params["collector"] = collector
    result = client.get("/collect/logs", params)
    format_result(result, table=table)


@collect_app.command("settings")
def collect_settings(
    name: Annotated[
        str | None,
        typer.Argument(help="采集器名称，不指定则显示全部"),
    ] = None,
    interval: Annotated[
        int | None,
        typer.Option("--interval", "-i", help="设置采集间隔（秒）"),
    ] = None,
    active: Annotated[
        bool | None,
        typer.Option("--active/--inactive", help="启用/禁用采集器"),
    ] = None,
) -> None:
    """查询或更新采集器配置."""
    client = APIClient()

    if not name:
        result = client.get("/collect/settings")
        format_result(result)
        return

    if interval is None and active is None:
        result = client.get("/collect/settings")
        format_result(result)
        return

    body: dict = {}
    if interval is not None:
        body["interval_seconds"] = interval
    if active is not None:
        body["is_active"] = active
    result = client.put(f"/collect/settings/{name}", body)
    format_result(result)
