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
        tools: list[dict] | None = None,
    ) -> str:
        logger.debug(
            "Calling %s/%s: %d messages%s",
            self._provider_type, self._model, len(messages),
            " (with tools)" if tools else "",
        )
        kwargs: dict = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            kwargs["tools"] = tools
        resp = await self._client.chat.completions.create(**kwargs)
        choice = resp.choices[0]
        content = choice.message.content or ""
        return content

    async def analyze(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.3,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        tools: list[dict] | None = None,
    ) -> dict[str, Any]:
        """Send a structured analysis request with JSON output.

        Returns parsed dict on success.  Returns {"error": ..., "raw": ...}
        on parse failure so callers don't crash on malformed responses.
        Optional tools (e.g. web_search) are passed to the model.
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        def _parse_json_safe(text: str) -> dict:
            """安全解析 AI 返回文本为 JSON，剥离 markdown 代码块标记。"""
            text = text.strip()
            if text.startswith("```"):
                for marker in ("```json\n", "```\n"):
                    if text.startswith(marker):
                        text = text[len(marker):]
                        break
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                logger.warning(
                    "%s returned non-JSON (first 200): %s",
                    self._provider_type, text[:200],
                )
                return {"error": "JSON_PARSE_FAILED", "raw": text}

        # 第一轮：带 tools 调用（AI 可联网搜索）
        if tools:
            resp = await self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                tools=tools,
            )
            choice = resp.choices[0]
            raw_content = choice.message.content or ""
            # DeepSeek 可能用 XML 格式返回 tool call
            if choice.message.tool_calls or "<invoke name=" in raw_content:
                if choice.message.tool_calls:
                    for tc in choice.message.tool_calls:
                        # DeepSeek 思考模式要求 assistant 消息必须含 reasoning_content
                        msg = {"role": "assistant", "content": None, "tool_calls": [{
                            "id": tc.id, "type": "function",
                            "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                        }]}
                        msg["reasoning_content"] = ""
                        messages.append(msg)
                        messages.append({"role": "tool", "tool_call_id": tc.id, "content": "搜索完成"})
                else:
                    messages.append({"role": "assistant", "content": raw_content})
                    messages.append({"role": "user", "content": "请结合搜索结果以JSON格式回复"})
                resp = await self._client.chat.completions.create(
                    model=self._model, messages=messages, temperature=temperature, max_tokens=max_tokens,
                )
                return _parse_json_safe(resp.choices[0].message.content or "")
            return _parse_json_safe(raw_content)

        # 无工具模式：直接请求 JSON
        text = await self.chat(messages=messages, temperature=temperature, max_tokens=max_tokens)
        return _parse_json_safe(text)


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
