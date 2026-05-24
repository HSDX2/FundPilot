"""Tests for collection control API endpoints."""

from unittest.mock import AsyncMock

from httpx import AsyncClient

from app.api.deps import get_collector_service, get_collector_setting_repo
from app.services.collector_service import CollectResult


class TestTriggerCollect:
    async def test_trigger_valid_collector(self, app, async_client: AsyncClient):
        """POST /api/v1/collect/trigger should run a valid collector."""
        mock_service = AsyncMock()
        mock_service.collect_etf_spot.return_value = CollectResult(
            records_added=10
        )

        async def _override():
            yield mock_service

        app.dependency_overrides[get_collector_service] = _override

        resp = await async_client.post(
            "/api/v1/collect/trigger",
            json={"collector": "etf"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["records_added"] == 10

        app.dependency_overrides.clear()

    async def test_trigger_invalid_collector(self, app, async_client: AsyncClient):
        """Unknown collector should return 404."""
        mock_service = AsyncMock()

        async def _override():
            yield mock_service

        app.dependency_overrides[get_collector_service] = _override

        resp = await async_client.post(
            "/api/v1/collect/trigger",
            json={"collector": "unknown"},
        )
        assert resp.status_code == 404
        data = resp.json()
        assert data["error"]["code"] == "COLLECTOR_NOT_FOUND"

        app.dependency_overrides.clear()

    async def test_trigger_news_with_sources(self, app, async_client: AsyncClient):
        """Triggering news collector with sources should pass them through."""
        from app.services.collector_service import CollectResult

        mock_service = AsyncMock()
        mock_service.collect_news.return_value = CollectResult(records_added=5)

        async def _override():
            yield mock_service

        app.dependency_overrides[get_collector_service] = _override

        resp = await async_client.post(
            "/api/v1/collect/trigger",
            json={
                "collector": "news",
                "sources": ["eastmoney", "jin10"],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["records_added"] == 5
        mock_service.collect_news.assert_called_once_with(
            sources=["eastmoney", "jin10"]
        )

        app.dependency_overrides.clear()

    async def test_trigger_news_without_sources(self, app, async_client: AsyncClient):
        """Triggering news without sources should pass None (collect all)."""
        from app.services.collector_service import CollectResult

        mock_service = AsyncMock()
        mock_service.collect_news.return_value = CollectResult(records_added=10)

        async def _override():
            yield mock_service

        app.dependency_overrides[get_collector_service] = _override

        resp = await async_client.post(
            "/api/v1/collect/trigger",
            json={"collector": "news"},
        )
        assert resp.status_code == 200
        mock_service.collect_news.assert_called_once_with(sources=None)

        app.dependency_overrides.clear()

    async def test_trigger_with_missing_body(self, app, async_client: AsyncClient):
        """Missing body should return 422."""
        resp = await async_client.post(
            "/api/v1/collect/trigger", json={}
        )
        assert resp.status_code == 422


class TestCollectorSettings:
    async def test_list_settings(self, app, async_client: AsyncClient):
        """GET /api/v1/collect/settings should return settings list."""
        mock_repo = AsyncMock()
        mock_repo.list.return_value = []

        async def _override():
            yield mock_repo

        app.dependency_overrides[get_collector_setting_repo] = _override

        resp = await async_client.get("/api/v1/collect/settings")
        assert resp.status_code == 200
        assert resp.json()["data"]["items"] == []

        app.dependency_overrides.clear()

    async def test_update_setting_success(self, app, async_client: AsyncClient):
        """Successful update should return updated setting."""
        import uuid
        from unittest.mock import MagicMock

        uid = uuid.uuid4()
        original = MagicMock()
        original.id = uid
        original.collector_name = "etf"
        original.display_name = "ETF实时采集"
        original.interval_seconds = 30
        original.is_active = True
        original.schedule_config = None
        original.last_run_at = None
        original.last_status = None

        mock_repo = AsyncMock()
        mock_repo.get_by_name.return_value = original

        async def _override():
            yield mock_repo

        app.dependency_overrides[get_collector_setting_repo] = _override

        resp = await async_client.put(
            "/api/v1/collect/settings/etf",
            json={"interval_seconds": 60, "is_active": False},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True

        app.dependency_overrides.clear()

    async def test_update_setting_not_found(
        self, app, async_client: AsyncClient
    ):
        """Updating non-existent collector should return 404."""
        mock_repo = AsyncMock()
        mock_repo.get_by_name.return_value = None

        async def _override():
            yield mock_repo

        app.dependency_overrides[get_collector_setting_repo] = _override

        resp = await async_client.put(
            "/api/v1/collect/settings/unknown",
            json={"interval_seconds": 60},
        )
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "COLLECTOR_NOT_FOUND"

        app.dependency_overrides.clear()

    async def test_update_schedule_success(
        self, app, async_client: AsyncClient,
    ):
        """PUT /settings/{name}/schedule should merge and return setting."""
        import uuid
        from unittest.mock import MagicMock

        uid = uuid.uuid4()
        config = {"mode": "interval", "interval_minutes": 30}

        original = MagicMock()
        original.id = uid
        original.collector_name = "etf"
        original.display_name = "ETF实时采集"
        original.interval_seconds = 30
        original.is_active = True
        original.schedule_config = dict(config)
        original.last_run_at = None
        original.last_status = None

        mock_repo = AsyncMock()
        mock_repo.get_by_name.return_value = original

        async def _override():
            yield mock_repo

        app.dependency_overrides[get_collector_setting_repo] = _override

        resp = await async_client.put(
            "/api/v1/collect/settings/etf/schedule",
            json={
                "mode": "specific_time",
                "specific_time": "12:00:00",
                "weekdays": [1, 2, 3, 4, 5],
            },
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

        app.dependency_overrides.clear()

    async def test_update_schedule_not_found(
        self, app, async_client: AsyncClient,
    ):
        """PUT /settings/{name}/schedule with unknown name returns 404."""
        mock_repo = AsyncMock()
        mock_repo.get_by_name.return_value = None

        async def _override():
            yield mock_repo

        app.dependency_overrides[get_collector_setting_repo] = _override

        resp = await async_client.put(
            "/api/v1/collect/settings/unknown/schedule",
            json={"interval_minutes": 60},
        )
        assert resp.status_code == 404

        app.dependency_overrides.clear()
