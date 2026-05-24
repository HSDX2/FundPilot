"""OpenAI-compatible API adapter.

Works with any provider that follows OpenAI's /v1/chat/completions format:
  - DeepSeek    https://api.deepseek.com/v1
  - GLM (智谱)   https://open.bigmodel.cn/api/paas/v4
  - QWEN (通义)  https://dashscope.aliyuncs.com/compatible-mode/v1
  - OpenAI      https://api.openai.com/v1
  - Kimi (月暗)  https://api.moonshot.cn/v1
  - MiniMax     https://api.minimax.chat/v1
"""

import json
import logging
from typing import Any

from openai import AsyncOpenAI

from app.ai.base import AIProvider

logger = logging.getLogger(__name__)

# All known providers support at least 4096 output tokens
DEFAULT_MAX_TOKENS = 4096


class OpenAICompatibleProvider(AIProvider):
    """Adapts any OpenAI-compatible API into the AIProvider interface."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        provider_type: str,
    ) -> None:
        self._base_url = base_url
        self._model = model
        self._provider_type = provider_type
        self._client = AsyncOpenAI(
            base_url=base_url,
            api_key=api_key,
        )

    @property
    def provider_type(self) -> str:
        return self._provider_type

    @property
    def model(self) -> str:
        return self._model

    async def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> str:
        logger.debug(
            "Calling %s/%s: %d messages",
            self._provider_type, self._model, len(messages),
        )
        resp = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,  # type: ignore[arg-type]
            temperature=temperature,
            max_tokens=max_tokens,
        )
        choice = resp.choices[0]
        content = choice.message.content or ""
        return content

    async def analyze(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.3,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> dict[str, Any]:
        """Send a structured analysis request with JSON output.

        Returns parsed dict on success.  Returns {"error": ..., "raw": ...}
        on parse failure so callers don't crash on malformed responses.
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        text = await self.chat(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        try:
            return json.loads(text)  # type: ignore[no-any-return]
        except json.JSONDecodeError:
            logger.warning(
                "%s returned non-JSON response (first 200 chars): %s",
                self._provider_type,
                text[:200],
            )
            return {"error": "JSON_PARSE_FAILED", "raw": text}


# ── Provider preset registry ─────────────────────────────────────────


PROVIDER_PRESETS: dict[str, dict[str, str]] = {
    "deepseek": {
        "name": "DeepSeek",
        "base_url": "https://api.deepseek.com/v1",
        "default_model": "deepseek-chat",
    },
    "glm": {
        "name": "智谱 GLM",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "default_model": "glm-4-flash",
    },
    "qwen": {
        "name": "通义千问",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "default_model": "qwen-turbo",
    },
    "openai": {
        "name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4o-mini",
    },
    "kimi": {
        "name": "Kimi 月之暗面",
        "base_url": "https://api.moonshot.cn/v1",
        "default_model": "moonshot-v1-8k",
    },
    "minimax": {
        "name": "MiniMax",
        "base_url": "https://api.minimax.chat/v1",
        "default_model": "abab6.5s-chat",
    },
}
