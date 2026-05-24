"""Tests for AI Provider management API endpoints."""

import uuid
from unittest.mock import AsyncMock, MagicMock

from httpx import AsyncClient

from app.api.deps import get_ai_provider_repo


class TestListAIProviders:
    async def test_empty_list(self, app, async_client: AsyncClient):
        mock_repo = AsyncMock()
        mock_repo.list_by_types.return_value = []

        async def _override():
            yield mock_repo

        app.dependency_overrides[get_ai_provider_repo] = _override

        resp = await async_client.get("/api/v1/admin/ai-providers")
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["items"] == []
        assert data["data"]["total"] == 0

        app.dependency_overrides.clear()

    async def test_list_with_filter(self, app, async_client: AsyncClient):
        uid = uuid.uuid4()
        mock_provider = MagicMock()
        mock_provider.id = uid
        mock_provider.name = "DeepSeek"
        mock_provider.provider_type = "deepseek"
        mock_provider.api_base_url = "https://api.deepseek.com/v1"
        mock_provider.model_name = "deepseek-chat"
        mock_provider.is_active = True
        mock_provider.extra_config = None

        mock_repo = AsyncMock()
        mock_repo.list_by_types.return_value = [mock_provider]

        async def _override():
            yield mock_repo

        app.dependency_overrides[get_ai_provider_repo] = _override

        resp = await async_client.get(
            "/api/v1/admin/ai-providers?provider_type=deepseek,openai"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["total"] == 1
        mock_repo.list_by_types.assert_called_once_with(
            provider_types=["deepseek", "openai"]
        )

        app.dependency_overrides.clear()

    async def test_list_no_filter(self, app, async_client: AsyncClient):
        mock_repo = AsyncMock()
        mock_repo.list_by_types.return_value = []

        async def _override():
            yield mock_repo

        app.dependency_overrides[get_ai_provider_repo] = _override

        resp = await async_client.get("/api/v1/admin/ai-providers")
        assert resp.status_code == 200
        mock_repo.list_by_types.assert_called_once_with(provider_types=None)

        app.dependency_overrides.clear()


class TestGetActiveProvider:
    async def test_no_active_provider(self, app, async_client: AsyncClient):
        mock_repo = AsyncMock()
        mock_repo.get_active.return_value = None

        async def _override():
            yield mock_repo

        app.dependency_overrides[get_ai_provider_repo] = _override

        resp = await async_client.get("/api/v1/admin/ai-providers/active")
        assert resp.status_code == 200
        assert resp.json()["data"] is None

        app.dependency_overrides.clear()

    async def test_with_active_provider(self, app, async_client: AsyncClient):
        uid = uuid.uuid4()
        mock = MagicMock()
        mock.id = uid
        mock.name = "OpenAI"
        mock.provider_type = "openai"
        mock.api_base_url = "https://api.openai.com/v1"
        mock.model_name = "gpt-4o"
        mock.is_active = True
        mock.extra_config = None

        mock_repo = AsyncMock()
        mock_repo.get_active.return_value = mock

        async def _override():
            yield mock_repo

        app.dependency_overrides[get_ai_provider_repo] = _override

        resp = await async_client.get("/api/v1/admin/ai-providers/active")
        assert resp.status_code == 200
        assert resp.json()["data"]["name"] == "OpenAI"

        app.dependency_overrides.clear()


class TestCreateAIProvider:
    async def test_create_success(self, app, async_client: AsyncClient):
        mock_repo = AsyncMock()

        async def _override():
            yield mock_repo

        app.dependency_overrides[get_ai_provider_repo] = _override

        resp = await async_client.post(
            "/api/v1/admin/ai-providers",
            json={
                "name": "DeepSeek",
                "provider_type": "deepseek",
                "api_key": "sk-test",
                "api_base_url": "https://api.deepseek.com/v1",
                "model_name": "deepseek-chat",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["name"] == "DeepSeek"

        app.dependency_overrides.clear()

    async def test_create_missing_required(self, app, async_client: AsyncClient):
        mock_repo = AsyncMock()

        async def _override():
            yield mock_repo

        app.dependency_overrides[get_ai_provider_repo] = _override

        resp = await async_client.post(
            "/api/v1/admin/ai-providers",
            json={"name": "Incomplete"},
        )
        assert resp.status_code == 422

        app.dependency_overrides.clear()


class TestGetAIProvider:
    async def test_not_found(self, app, async_client: AsyncClient):
        mock_repo = AsyncMock()
        mock_repo.get.return_value = None

        async def _override():
            yield mock_repo

        app.dependency_overrides[get_ai_provider_repo] = _override

        resp = await async_client.get(
            f"/api/v1/admin/ai-providers/{uuid.uuid4()}"
        )
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "AI_PROVIDER_NOT_FOUND"

        app.dependency_overrides.clear()

    async def test_invalid_uuid_format(self, app, async_client: AsyncClient):
        mock_repo = AsyncMock()

        async def _override():
            yield mock_repo

        app.dependency_overrides[get_ai_provider_repo] = _override

        resp = await async_client.get("/api/v1/admin/ai-providers/not-a-uuid")
        assert resp.status_code == 400

        app.dependency_overrides.clear()


class TestUpdateAIProvider:
    async def test_update_success(self, app, async_client: AsyncClient):
        uid = uuid.uuid4()
        mock = MagicMock()
        mock.id = uid
        mock.name = "Old Name"
        mock.provider_type = "deepseek"
        mock.api_base_url = "https://api.deepseek.com/v1"
        mock.model_name = "deepseek-chat"
        mock.is_active = False
        mock.extra_config = None

        updated = MagicMock()
        updated.id = uid
        updated.name = "New Name"
        updated.provider_type = "deepseek"
        updated.api_base_url = "https://api.deepseek.com/v1"
        updated.model_name = "deepseek-chat"
        updated.is_active = False
        updated.extra_config = None

        mock_repo = AsyncMock()
        mock_repo.get.side_effect = [mock, updated]
        mock_repo.update = AsyncMock()

        async def _override():
            yield mock_repo

        app.dependency_overrides[get_ai_provider_repo] = _override

        resp = await async_client.put(
            f"/api/v1/admin/ai-providers/{uid}",
            json={"name": "New Name"},
        )
        assert resp.status_code == 200

        app.dependency_overrides.clear()

    async def test_update_not_found(self, app, async_client: AsyncClient):
        mock_repo = AsyncMock()
        mock_repo.get.return_value = None

        async def _override():
            yield mock_repo

        app.dependency_overrides[get_ai_provider_repo] = _override

        resp = await async_client.put(
            f"/api/v1/admin/ai-providers/{uuid.uuid4()}",
            json={"name": "New Name"},
        )
        assert resp.status_code == 404

        app.dependency_overrides.clear()


class TestDeleteAIProvider:
    async def test_delete_success(self, app, async_client: AsyncClient):
        uid = uuid.uuid4()
        mock = MagicMock()
        mock.id = uid
        mock.is_active = False

        mock_repo = AsyncMock()
        mock_repo.get.return_value = mock
        mock_repo.delete = AsyncMock()

        async def _override():
            yield mock_repo

        app.dependency_overrides[get_ai_provider_repo] = _override

        resp = await async_client.delete(f"/api/v1/admin/ai-providers/{uid}")
        assert resp.status_code == 200

        app.dependency_overrides.clear()

    async def test_cannot_delete_active(self, app, async_client: AsyncClient):
        uid = uuid.uuid4()
        mock = MagicMock()
        mock.id = uid
        mock.is_active = True

        mock_repo = AsyncMock()
        mock_repo.get.return_value = mock

        async def _override():
            yield mock_repo

        app.dependency_overrides[get_ai_provider_repo] = _override

        resp = await async_client.delete(f"/api/v1/admin/ai-providers/{uid}")
        assert resp.status_code == 400

        app.dependency_overrides.clear()


class TestActivateAIProvider:
    async def test_activate_success(self, app, async_client: AsyncClient):
        uid = uuid.uuid4()
        mock = MagicMock()
        mock.id = uid
        mock.name = "DeepSeek"
        mock.provider_type = "deepseek"
        mock.api_base_url = "https://api.deepseek.com/v1"
        mock.model_name = "deepseek-chat"
        mock.is_active = True
        mock.extra_config = None

        mock_repo = AsyncMock()
        mock_repo.get.side_effect = [mock, mock]  # before + after
        mock_repo.set_active = AsyncMock(return_value=mock)

        async def _override():
            yield mock_repo

        app.dependency_overrides[get_ai_provider_repo] = _override

        resp = await async_client.post(
            f"/api/v1/admin/ai-providers/{uid}/activate"
        )
        assert resp.status_code == 200
        mock_repo.set_active.assert_called_once_with(uid)

        app.dependency_overrides.clear()

    async def test_activate_not_found(self, app, async_client: AsyncClient):
        mock_repo = AsyncMock()
        mock_repo.get.return_value = None

        async def _override():
            yield mock_repo

        app.dependency_overrides[get_ai_provider_repo] = _override

        resp = await async_client.post(
            f"/api/v1/admin/ai-providers/{uuid.uuid4()}/activate"
        )
        assert resp.status_code == 404

        app.dependency_overrides.clear()
