"""Tests for AnalysisService."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.ai.base import AIProvider
from app.services.analysis_service import AnalysisService


class FakeAI(AIProvider):
    """Fake AI provider that returns predefined JSON."""

    def __init__(self, response: dict, provider_type: str = "test"):
        self._response = response
        self._ptype = provider_type

    @property
    def provider_type(self) -> str:
        return self._ptype

    @property
    def model(self) -> str:
        return "test-model"

    async def chat(self, messages, temperature=0.3, max_tokens=4096) -> str:
        import json
        return json.dumps(self._response)

    async def analyze(
        self, system_prompt: str, user_prompt: str,
        temperature=0.3, max_tokens=4096,
    ) -> dict:
        return self._response


def _make_async_mock(**methods):
    """Make a MagicMock where specified methods are AsyncMock."""
    mock = MagicMock()
    mock.session = MagicMock()
    mock.session.add = MagicMock()
    mock.session.flush = AsyncMock()
    for name, return_value in methods.items():
        setattr(mock, name, AsyncMock(return_value=return_value))
    return mock


def _make_service(ai_resp: dict | None = None) -> AnalysisService:
    if ai_resp is None:
        ai_resp = {
            "summary": "test",
            "trend": "up",
            "strength_score": 70,
            "risk_level": "medium",
            "key_factors": ["factor1"],
            "support_level": "-",
            "resistance_level": "-",
            "volume_analysis": "-",
            "money_flow_analysis": "-",
            "outlook": "-",
        }

    svc = AnalysisService(
        ai_provider_repo=_make_async_mock(),
        analysis_report_repo=_make_async_mock(),
        fund_advice_repo=_make_async_mock(),
        sector_repo=_make_async_mock(),
        sector_snapshot_repo=_make_async_mock(),
        sector_money_flow_repo=_make_async_mock(),
        fund_repo=_make_async_mock(),
        fund_nav_repo=_make_async_mock(),
        fund_estimate_repo=_make_async_mock(),
        news_repo=_make_async_mock(),
    )

    class _ActiveProvider:
        api_base_url = "https://api.test.com/v1"
        api_key = "sk-test"
        model_name = "test-model"
        provider_type = "test"

    svc._ai_provider_repo.get_active = AsyncMock(return_value=_ActiveProvider())

    return svc


class TestGenerateSectorReport:
    @pytest.mark.asyncio
    async def test_success(self):
        svc = _make_service()
        with patch.object(
            svc, "_get_provider",
            return_value=FakeAI(
                {"summary": "bullish", "trend": "up", "strength_score": 85},
            ),
        ):
            from uuid import uuid4
            sector_mock = MagicMock()
            sector_mock.name = "新能源"
            sector_mock.category = "概念板块"
            svc._sector_repo.get = AsyncMock(return_value=sector_mock)
            svc._snapshot_repo.get_latest_by_sector = AsyncMock(return_value=None)
            svc._snapshot_repo.get_by_sector_and_time_range = AsyncMock(return_value=[])
            svc._money_flow_repo.get_by_sector_and_date = AsyncMock(return_value=None)
            svc._news_repo.search = AsyncMock(return_value=([], 0))

            report = await svc.generate_sector_report(uuid4(), "daily")
            assert report.report_type == "daily"
            assert report.content["summary"] == "bullish"
            assert report.ai_model == "test-model"

    @pytest.mark.asyncio
    async def test_sector_not_found(self):
        svc = _make_service()
        svc._sector_repo.get = AsyncMock(return_value=None)
        from uuid import uuid4
        with pytest.raises(ValueError, match="not found"):
            await svc.generate_sector_report(uuid4(), "daily")


class TestGenerateFundAdvice:
    @pytest.mark.asyncio
    async def test_success(self):
        svc = _make_service()
        with patch.object(
            svc, "_get_provider",
            return_value=FakeAI({
                "action": "buy",
                "confidence": 80,
                "reason": {"technical": "bullish"},
            }),
        ):
            from uuid import uuid4
            fund_mock = MagicMock()
            fund_mock.name = "测试基金"
            fund_mock.code = "000001"
            fund_mock.type = "股票型"
            svc._fund_repo.get = AsyncMock(return_value=fund_mock)
            svc._nav_repo.get_by_fund_and_date_range = AsyncMock(return_value=[])
            svc._est_repo.get_latest_by_fund = AsyncMock(return_value=None)
            svc._news_repo.search = AsyncMock(return_value=([], 0))

            advice = await svc.generate_fund_advice(uuid4())
            assert advice.action == "buy"
            assert advice.confidence == 80.0
            assert advice.ai_model == "test-model"

    @pytest.mark.asyncio
    async def test_invalid_action_falls_back_to_hold(self):
        svc = _make_service()
        with patch.object(
            svc, "_get_provider",
            return_value=FakeAI({
                "action": "invalid_action",
                "confidence": 50,
                "reason": {},
            }),
        ):
            from uuid import uuid4
            fund_mock = MagicMock()
            fund_mock.name = "X"
            fund_mock.code = "X"
            fund_mock.type = "X"
            svc._fund_repo.get = AsyncMock(return_value=fund_mock)
            svc._nav_repo.get_by_fund_and_date_range = AsyncMock(return_value=[])
            svc._est_repo.get_latest_by_fund = AsyncMock(return_value=None)
            svc._news_repo.search = AsyncMock(return_value=([], 0))

            advice = await svc.generate_fund_advice(uuid4())
            assert advice.action == "hold"

    @pytest.mark.asyncio
    async def test_fund_not_found(self):
        svc = _make_service()
        svc._fund_repo.get = AsyncMock(return_value=None)
        from uuid import uuid4
        with pytest.raises(ValueError, match="not found"):
            await svc.generate_fund_advice(uuid4())


class TestNoActiveProvider:
    @pytest.mark.asyncio
    async def test_raises_runtime_error(self):
        svc = _make_service()
        svc._ai_provider_repo.get_active = AsyncMock(return_value=None)
        from uuid import uuid4
        with pytest.raises(RuntimeError, match="No active AI provider"):
            await svc.generate_sector_report(uuid4(), "daily")
