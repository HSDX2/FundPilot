"""FundPilot CLI — command-line interface to the FundPilot API.

Usage:
    fundpilot fund search --name 新能源
    fundpilot sector rank --category concept --limit 10
    fundpilot collect trigger news
    fundpilot analysis report-latest
"""

from __future__ import annotations

import typer

from fundpilot.commands.analysis import analysis_app
from fundpilot.commands.collect import collect_app
from fundpilot.commands.fund import fund_app
from fundpilot.commands.news import news_app
from fundpilot.commands.sector import sector_app

app = typer.Typer(
    name="fundpilot",
    help="FundPilot CLI — 中国基金分析平台命令行工具",
    no_args_is_help=True,
)

app.add_typer(fund_app, name="fund", help="基金查询与估值")
app.add_typer(sector_app, name="sector", help="板块查询与排行")
app.add_typer(analysis_app, name="analysis", help="AI 分析报告与建议")
app.add_typer(news_app, name="news", help="新闻查询")
app.add_typer(collect_app, name="collect", help="采集控制与监控")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
