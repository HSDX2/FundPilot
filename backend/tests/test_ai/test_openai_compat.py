"""Tests for OpenAI-compatible provider adapter."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.ai.openai_compat import (
    PROVIDER_PRESETS,
    OpenAICompatibleProvider,
)


class TestOpenAICompatibleProvider:
    def test_properties(self):
        provider = OpenAICompatibleProvider(
            base_url="https://api.example.com/v1",
            api_key="sk-test-key",
            model="test-model",
            provider_type="custom",
        )
        assert provider.provider_type == "custom"
        assert provider.model == "test-model"

    @pytest.mark.asyncio
    async def test_chat_success(self):
        provider = OpenAICompatibleProvider(
            base_url="https://api.example.com/v1",
            api_key="sk-test-key",
            model="test-model",
            provider_type="custom",
        )
        mock_choice = MagicMock()
        mock_choice.message.content = "Hello from AI"
        mock_resp = MagicMock()
        mock_resp.choices = [mock_choice]
        provider._client.chat.completions.create = AsyncMock(
            return_value=mock_resp
        )

        result = await provider.chat(
            messages=[{"role": "user", "content": "Hi"}],
        )
        assert result == "Hello from AI"

    @pytest.mark.asyncio
    async def test_chat_empty_content(self):
        """None content should be coerced to empty string."""
        provider = OpenAICompatibleProvider(
            base_url="https://api.example.com/v1",
            api_key="sk-test-key",
            model="test-model",
            provider_type="custom",
        )
        mock_choice = MagicMock()
        mock_choice.message.content = None
        mock_resp = MagicMock()
        mock_resp.choices = [mock_choice]
        provider._client.chat.completions.create = AsyncMock(
            return_value=mock_resp
        )

        result = await provider.chat(
            messages=[{"role": "user", "content": "Hi"}],
        )
        assert result == ""

    @pytest.mark.asyncio
    async def test_chat_passes_temperature_and_max_tokens(self):
        provider = OpenAICompatibleProvider(
            base_url="https://api.example.com/v1",
            api_key="sk-test-key",
            model="test-model",
            provider_type="custom",
        )
        mock_choice = MagicMock()
        mock_choice.message.content = "OK"
        mock_resp = MagicMock()
        mock_resp.choices = [mock_choice]
        provider._client.chat.completions.create = AsyncMock(
            return_value=mock_resp
        )

        await provider.chat(
            messages=[{"role": "user", "content": "Hi"}],
            temperature=0.7,
            max_tokens=2048,
        )
        call_kwargs = provider._client.chat.completions.create.call_args.kwargs
        assert call_kwargs["temperature"] == 0.7
        assert call_kwargs["max_tokens"] == 2048

    @pytest.mark.asyncio
    async def test_analyze_returns_parsed_dict(self):
        provider = OpenAICompatibleProvider(
            base_url="https://api.example.com/v1",
            api_key="sk-test-key",
            model="test-model",
            provider_type="custom",
        )
        json_output = json.dumps({"score": 85, "label": "bullish"})
        mock_choice = MagicMock()
        mock_choice.message.content = json_output
        mock_resp = MagicMock()
        mock_resp.choices = [mock_choice]
        provider._client.chat.completions.create = AsyncMock(
            return_value=mock_resp
        )

        result = await provider.analyze(
            system_prompt="You are an analyst.",
            user_prompt="Analyze market sentiment.",
        )
        assert result == {"score": 85, "label": "bullish"}

    @pytest.mark.asyncio
    async def test_analyze_non_json_response(self):
        """Non-JSON response should return error dict instead of raising."""
        provider = OpenAICompatibleProvider(
            base_url="https://api.example.com/v1",
            api_key="sk-test-key",
            model="test-model",
            provider_type="custom",
        )
        mock_choice = MagicMock()
        mock_choice.message.content = "This is not valid JSON!"
        mock_resp = MagicMock()
        mock_resp.choices = [mock_choice]
        provider._client.chat.completions.create = AsyncMock(
            return_value=mock_resp
        )

        result = await provider.analyze(
            system_prompt="You are an analyst.",
            user_prompt="Analyze.",
        )
        assert result["error"] == "JSON_PARSE_FAILED"
        assert result["raw"] == "This is not valid JSON!"


class TestProviderPresets:
    def test_all_presets_have_required_keys(self):
        for ptype, preset in PROVIDER_PRESETS.items():
            assert "name" in preset, f"{ptype} missing name"
            assert "base_url" in preset, f"{ptype} missing base_url"
            assert "default_model" in preset, f"{ptype} missing default_model"

    def test_preset_types_match_enum(self):
        from app.core.constants import AIProviderType
        known = {m.value for m in AIProviderType}
        for ptype in PROVIDER_PRESETS:
            assert ptype in known, f"{ptype} not in AIProviderType"
