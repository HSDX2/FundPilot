"""Tests for AI-related schemas."""

import pytest
from pydantic import ValidationError

from app.schemas.ai import (
    AIProviderCreate,
    AIProviderListData,
    AIProviderResponse,
    AIProviderUpdate,
)


class TestAIProviderCreate:
    def test_minimal_valid(self):
        body = AIProviderCreate(
            name="Test Provider",
            provider_type="deepseek",
            api_key="sk-test",
            api_base_url="https://api.test.com/v1",
            model_name="test-model",
        )
        assert body.name == "Test Provider"
        assert body.extra_config is None

    def test_with_extra_config(self):
        body = AIProviderCreate(
            name="Test Provider",
            provider_type="openai",
            api_key="sk-test",
            api_base_url="https://api.openai.com/v1",
            model_name="gpt-4o",
            extra_config={"temperature": 0.7, "max_tokens": 2048},
        )
        assert body.extra_config == {"temperature": 0.7, "max_tokens": 2048}

    def test_missing_required_fields(self):
        with pytest.raises(ValidationError):
            AIProviderCreate(name="Test")


class TestAIProviderUpdate:
    def test_empty_update(self):
        body = AIProviderUpdate()
        assert body.model_dump(exclude_none=True) == {}

    def test_partial_update(self):
        body = AIProviderUpdate(api_key="new-key")
        assert body.api_key == "new-key"
        assert body.name is None


class TestAIProviderResponse:
    def test_from_attributes(self):
        import uuid
        from unittest.mock import MagicMock

        uid = uuid.uuid4()
        mock = MagicMock()
        mock.id = uid
        mock.name = "DeepSeek"
        mock.provider_type = "deepseek"
        mock.api_base_url = "https://api.deepseek.com/v1"
        mock.model_name = "deepseek-chat"
        mock.is_active = True
        mock.extra_config = {"temperature": 0.3}

        resp = AIProviderResponse.model_validate(mock)
        assert resp.id == uid
        assert resp.name == "DeepSeek"
        assert resp.is_active is True


class TestAIProviderListData:
    def test_basic(self):
        data = AIProviderListData(items=[], total=0)
        assert data.items == []
        assert data.total == 0
