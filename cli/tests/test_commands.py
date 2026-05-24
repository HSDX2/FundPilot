"""Integration tests for CLI commands (CliRunner + mocked HTTP)."""

from __future__ import annotations

import httpx
from typer.testing import CliRunner

from fundpilot.main import app

runner = CliRunner()

API = "http://localhost:8000/api/v1"
_JSON = lambda d: httpx.Response(200, json=d)  # noqa: E731


class TestFundCommands:
    def test_search_no_args(self, respx_mock) -> None:
        respx_mock.get(f"{API}/funds").mock(
            return_value=_JSON(
                {"success": True, "data": {"items": [], "total": 0}}
            )
        )
        result = runner.invoke(app, ["fund", "search"])
        assert result.exit_code == 0

    def test_search_with_name(self, respx_mock) -> None:
        route = respx_mock.get(
            f"{API}/funds?page=1&page_size=20&name=test"
        ).mock(
            return_value=_JSON(
                {"success": True, "data": {"items": [], "total": 0}}
            )
        )
        result = runner.invoke(app, ["fund", "search", "--name", "test"])
        assert result.exit_code == 0
        assert route.called

    def test_detail(self, respx_mock) -> None:
        respx_mock.get(f"{API}/funds/000001").mock(
            return_value=_JSON(
                {"success": True, "data": {"code": "000001", "name": "Test"}}
            )
        )
        result = runner.invoke(app, ["fund", "detail", "000001"])
        assert result.exit_code == 0

    def test_nav(self, respx_mock) -> None:
        respx_mock.get(
            f"{API}/funds/000001/nav?start_date=2026-01-01"
        ).mock(return_value=_JSON({"success": True, "data": {"items": []}}))
        result = runner.invoke(
            app, ["fund", "nav", "000001", "--start", "2026-01-01"]
        )
        assert result.exit_code == 0

    def test_estimate(self, respx_mock) -> None:
        respx_mock.get(f"{API}/funds/000001/estimate").mock(
            return_value=_JSON({"success": True, "data": {}})
        )
        result = runner.invoke(app, ["fund", "estimate", "000001"])
        assert result.exit_code == 0

    def test_batch_estimate(self, respx_mock) -> None:
        respx_mock.get(f"{API}/funds/estimates/batch").mock(
            return_value=_JSON({"success": True, "data": {"items": []}})
        )
        result = runner.invoke(
            app, ["fund", "batch-estimate", "000001,000011"]
        )
        assert result.exit_code == 0


class TestSectorCommands:
    def test_search(self, respx_mock) -> None:
        respx_mock.get(
            f"{API}/sectors?page=1&page_size=20&category=concept"
        ).mock(
            return_value=_JSON(
                {"success": True, "data": {"items": [], "total": 0}}
            )
        )
        result = runner.invoke(
            app, ["sector", "search", "--category", "concept"]
        )
        assert result.exit_code == 0

    def test_rank(self, respx_mock) -> None:
        respx_mock.get(f"{API}/sectors/rank/current?limit=10").mock(
            return_value=_JSON(
                {"success": True, "data": {"items": [], "rank_time": "2026"}}
            )
        )
        result = runner.invoke(
            app, ["sector", "rank", "--limit", "10", "--table"]
        )
        assert result.exit_code == 0

    def test_money_flow(self, respx_mock) -> None:
        uid = "00000000-0000-0000-0000-000000000001"
        url = f"{API}/sectors/{uid}/money-flow?start_date=2026-05-01"
        respx_mock.get(url).mock(
            return_value=_JSON({"success": True, "data": {"items": []}})
        )
        result = runner.invoke(
            app, ["sector", "money-flow", uid, "--start", "2026-05-01"]
        )
        assert result.exit_code == 0


class TestAnalysisCommands:
    def test_report_list(self, respx_mock) -> None:
        respx_mock.get(f"{API}/analysis/reports").mock(
            return_value=_JSON(
                {"success": True, "data": {"items": [], "total": 0}}
            )
        )
        result = runner.invoke(app, ["analysis", "report-list"])
        assert result.exit_code == 0

    def test_report_latest(self, respx_mock) -> None:
        respx_mock.get(f"{API}/analysis/reports/latest").mock(
            return_value=_JSON({"success": True, "data": None})
        )
        result = runner.invoke(app, ["analysis", "report-latest"])
        assert result.exit_code == 0

    def test_advice_list(self, respx_mock) -> None:
        respx_mock.get(
            f"{API}/analysis/advice?page=1&page_size=20&action=buy"
        ).mock(
            return_value=_JSON(
                {"success": True, "data": {"items": [], "total": 0}}
            )
        )
        result = runner.invoke(
            app, ["analysis", "advice-list", "--action", "buy"]
        )
        assert result.exit_code == 0

    def test_sentiment_latest(self, respx_mock) -> None:
        respx_mock.get(f"{API}/analysis/sentiment/latest").mock(
            return_value=_JSON(
                {"success": True, "data": {"composite_score": 65.5}}
            )
        )
        result = runner.invoke(app, ["analysis", "sentiment-latest"])
        assert result.exit_code == 0


class TestNewsCommands:
    def test_search(self, respx_mock) -> None:
        respx_mock.get(
            f"{API}/news?page=1&page_size=20&keyword=test"
        ).mock(
            return_value=_JSON(
                {"success": True, "data": {"items": [], "total": 0}}
            )
        )
        result = runner.invoke(app, ["news", "search", "--keyword", "test"])
        assert result.exit_code == 0

    def test_detail(self, respx_mock) -> None:
        uid = "00000000-0000-0000-0000-000000000001"
        respx_mock.get(f"{API}/news/{uid}").mock(
            return_value=_JSON(
                {"success": True, "data": {"id": uid, "title": "News"}}
            )
        )
        result = runner.invoke(app, ["news", "detail", uid])
        assert result.exit_code == 0


class TestCollectCommands:
    def test_trigger(self, respx_mock) -> None:
        respx_mock.post(f"{API}/collect/trigger").mock(
            return_value=_JSON(
                {
                    "success": True,
                    "data": {"collector_name": "news", "records_added": 10},
                }
            )
        )
        result = runner.invoke(app, ["collect", "trigger", "news"])
        assert result.exit_code == 0

    def test_trigger_with_sources(self, respx_mock) -> None:
        route = respx_mock.post(f"{API}/collect/trigger").mock(
            return_value=_JSON(
                {
                    "success": True,
                    "data": {"collector_name": "news", "records_added": 5},
                }
            )
        )
        result = runner.invoke(
            app, ["collect", "trigger", "news", "--sources", "eastmoney,jin10"]
        )
        assert result.exit_code == 0
        assert route.called

    def test_status_all(self, respx_mock) -> None:
        respx_mock.get(f"{API}/collect/status").mock(
            return_value=_JSON({"success": True, "data": {"items": []}})
        )
        result = runner.invoke(app, ["collect", "status"])
        assert result.exit_code == 0

    def test_status_specific(self, respx_mock) -> None:
        respx_mock.get(f"{API}/collect/status/fund_list").mock(
            return_value=_JSON({"success": True, "data": {}})
        )
        result = runner.invoke(app, ["collect", "status", "fund_list"])
        assert result.exit_code == 0

    def test_stop(self, respx_mock) -> None:
        respx_mock.post(f"{API}/collect/stop/fund_nav").mock(
            return_value=_JSON(
                {"success": True, "data": {"stopped": True}}
            )
        )
        result = runner.invoke(app, ["collect", "stop", "fund_nav"])
        assert result.exit_code == 0

    def test_logs(self, respx_mock) -> None:
        respx_mock.get(
            f"{API}/collect/logs?page=1&page_size=20&collector=news"
        ).mock(
            return_value=_JSON(
                {"success": True, "data": {"items": [], "total": 0}}
            )
        )
        result = runner.invoke(
            app, ["collect", "logs", "--collector", "news"]
        )
        assert result.exit_code == 0

    def test_settings_view(self, respx_mock) -> None:
        respx_mock.get(f"{API}/collect/settings").mock(
            return_value=_JSON({"success": True, "data": {"items": []}})
        )
        result = runner.invoke(app, ["collect", "settings"])
        assert result.exit_code == 0

    def test_settings_update(self, respx_mock) -> None:
        respx_mock.put(f"{API}/collect/settings/fund_list").mock(
            return_value=_JSON({"success": True, "data": {}})
        )
        result = runner.invoke(
            app, ["collect", "settings", "fund_list", "--interval", "3600"]
        )
        assert result.exit_code == 0


class TestHelp:
    def test_main_help(self) -> None:
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "fund" in result.stdout
        assert "sector" in result.stdout
        assert "analysis" in result.stdout
        assert "news" in result.stdout
        assert "collect" in result.stdout

    def test_subcommand_help(self) -> None:
        for cmd in ["fund", "sector", "analysis", "news", "collect"]:
            result = runner.invoke(app, [cmd, "--help"])
            assert result.exit_code == 0, f"{cmd} --help failed"
