"""Tests for AI Analysis API endpoints."""

import uuid
from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock

from httpx import AsyncClient

from app.api.deps import get_analysis_service


class TestListReports:
    async def test_empty_list(self, app, async_client: AsyncClient):
        mock_svc = MagicMock()
        mock_svc._report_repo.list_by_type = AsyncMock(return_value=([], 0))

        async def _override():
            yield mock_svc

        app.dependency_overrides[get_analysis_service] = _override

        resp = await async_client.get("/api/v1/analysis/reports")
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["items"] == []
        assert data["data"]["total"] == 0

        app.dependency_overrides.clear()

    async def test_list_with_items(self, app, async_client: AsyncClient):
        from app.models.analysis import AnalysisReport

        report = MagicMock(spec=AnalysisReport)
        report.id = uuid.uuid4()
        report.date = date.today()
        report.report_type = "daily"
        report.content = {"summary": "test"}
        report.ai_model = "test-model"
        report.created_at = datetime.now()

        mock_svc = MagicMock()
        mock_svc._report_repo.list_by_type = AsyncMock(
            return_value=([report], 1),
        )

        async def _override():
            yield mock_svc

        app.dependency_overrides[get_analysis_service] = _override

        resp = await async_client.get("/api/v1/analysis/reports?report_type=daily")
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["total"] == 1
        assert data["data"]["items"][0]["report_type"] == "daily"

        app.dependency_overrides.clear()


class TestGetLatestReport:
    async def test_no_report(self, app, async_client: AsyncClient):
        mock_svc = MagicMock()
        mock_svc._report_repo.get_latest_by_type = AsyncMock(return_value=None)

        async def _override():
            yield mock_svc

        app.dependency_overrides[get_analysis_service] = _override

        resp = await async_client.get("/api/v1/analysis/reports/latest")
        assert resp.status_code == 200
        assert resp.json()["data"] is None

        app.dependency_overrides.clear()


class TestGetReport:
    async def test_not_found(self, app, async_client: AsyncClient):
        mock_svc = MagicMock()
        mock_svc._report_repo.get = AsyncMock(return_value=None)

        async def _override():
            yield mock_svc

        app.dependency_overrides[get_analysis_service] = _override

        resp = await async_client.get(
            f"/api/v1/analysis/reports/{uuid.uuid4()}",
        )
        assert resp.status_code == 404

        app.dependency_overrides.clear()

    async def test_invalid_uuid(self, app, async_client: AsyncClient):
        mock_svc = MagicMock()

        async def _override():
            yield mock_svc

        app.dependency_overrides[get_analysis_service] = _override

        resp = await async_client.get("/api/v1/analysis/reports/not-a-uuid")
        assert resp.status_code == 400

        app.dependency_overrides.clear()


class TestListAdvice:
    async def test_empty_list(self, app, async_client: AsyncClient):
        mock_svc = MagicMock()
        mock_svc._advice_repo.list_recent = AsyncMock(return_value=([], 0))

        async def _override():
            yield mock_svc

        app.dependency_overrides[get_analysis_service] = _override

        resp = await async_client.get("/api/v1/analysis/advice")
        assert resp.status_code == 200
        assert resp.json()["data"]["items"] == []

        app.dependency_overrides.clear()

    async def test_filter_by_action(self, app, async_client: AsyncClient):
        mock_svc = MagicMock()
        mock_svc._advice_repo.list_recent = AsyncMock(return_value=([], 0))

        async def _override():
            yield mock_svc

        app.dependency_overrides[get_analysis_service] = _override

        resp = await async_client.get("/api/v1/analysis/advice?action=buy")
        assert resp.status_code == 200
        mock_svc._advice_repo.list_recent.assert_called_once_with(
            page=1, page_size=20, action="buy",
        )

        app.dependency_overrides.clear()


class TestGetAdvice:
    async def test_not_found(self, app, async_client: AsyncClient):
        mock_svc = MagicMock()
        mock_svc._advice_repo.get = AsyncMock(return_value=None)

        async def _override():
            yield mock_svc

        app.dependency_overrides[get_analysis_service] = _override

        resp = await async_client.get(
            f"/api/v1/analysis/advice/{uuid.uuid4()}",
        )
        assert resp.status_code == 404

        app.dependency_overrides.clear()

    async def test_invalid_uuid(self, app, async_client: AsyncClient):
        mock_svc = MagicMock()

        async def _override():
            yield mock_svc

        app.dependency_overrides[get_analysis_service] = _override

        resp = await async_client.get("/api/v1/analysis/advice/not-a-uuid")
        assert resp.status_code == 400

        app.dependency_overrides.clear()


class TestGenerateReport:
    async def test_validation_missing_sector_id(self, app, async_client: AsyncClient):
        mock_svc = MagicMock()

        async def _override():
            yield mock_svc

        app.dependency_overrides[get_analysis_service] = _override

        resp = await async_client.post(
            "/api/v1/analysis/reports/generate",
            json={"report_type": "daily"},
        )
        assert resp.status_code == 422

        app.dependency_overrides.clear()


class TestGenerateAdvice:
    async def test_validation_missing_fund_id(self, app, async_client: AsyncClient):
        mock_svc = MagicMock()

        async def _override():
            yield mock_svc

        app.dependency_overrides[get_analysis_service] = _override

        resp = await async_client.post(
            "/api/v1/analysis/advice/generate",
            json={},
        )
        assert resp.status_code == 422

        app.dependency_overrides.clear()


class TestBatchSentiment:
    async def test_success(self, app, async_client: AsyncClient):
        mock_svc = MagicMock()
        mock_svc.batch_analyze_sentiment = AsyncMock(return_value=5)

        async def _override():
            yield mock_svc

        app.dependency_overrides[get_analysis_service] = _override

        resp = await async_client.post(
            "/api/v1/analysis/news/sentiment",
            json={"limit": 10},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["processed"] == 5

        app.dependency_overrides.clear()
