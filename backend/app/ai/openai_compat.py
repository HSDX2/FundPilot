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
            # 多轮 Tool Call 循环：支持 DeepSeek 连续多次调用工具
            MAX_ANALYZE_ROUNDS = 3
            _round = 0
            _has_tool_calls = (
                choice.message.tool_calls
                or "<invoke" in raw_content
                or "DSML" in raw_content
                or "<tool_calls" in raw_content
            )
            _current_content = raw_content

            while _has_tool_calls and _round < MAX_ANALYZE_ROUNDS:
                _round += 1
                _has_tool_calls = False

                # 解析并执行工具调用
                import re as _xml_re
                _result_parts = []

                if choice.message.tool_calls:
                    for tc in choice.message.tool_calls:
                        msg = {"role": "assistant", "content": None, "tool_calls": [{
                            "id": tc.id, "type": "function",
                            "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                        }]}
                        msg["reasoning_content"] = ""
                        messages.append(msg)
                        messages.append({"role": "tool", "tool_call_id": tc.id, "content": "搜索完成"})
                else:
                    # 标准 XML 格式
                    for _m in _xml_re.finditer(
                        r'<invoke name="(\w+)">.*?<parameter[^>]*>\s*(.*?)\s*</parameter>.*?</invoke>',
                        _current_content, _xml_re.DOTALL,
                    ):
                        _fn, _query = _m.group(1), _m.group(2)
                        if _fn == "web_search" and _query:
                            _result_parts.append(await _do_bing_search(_query, _xml_re))
                    # ｜DSML｜ 格式
                    for _m in _xml_re.finditer(
                        r'<｜DSML｜invoke[^>]*name="(\w+)"[^>]*>(.*?)</｜DSML｜invoke>',
                        _current_content, _xml_re.DOTALL,
                    ):
                        _fn = _m.group(1)
                        _qm = _xml_re.search(r'<parameter[^>]*>\s*(.*?)\s*</parameter>', _m.group(2), _xml_re.DOTALL)
                        _query = _qm.group(1) if _qm else ""
                        if _fn == "web_search" and _query:
                            _result_parts.append(await _do_bing_search(_query, _xml_re))

                    messages.append({"role": "assistant", "content": _current_content})
                    if _result_parts:
                        messages.append({"role": "user", "content": "\n".join(_result_parts) + "\n\n请基于以上搜索结果，以 JSON 格式输出分析结果，不要再调用搜索工具。"})
                    else:
                        messages.append({"role": "user", "content": "请基于已有数据以JSON格式输出分析结果，不要再调用搜索工具。"})

                # 下一轮 AI 调用
                if _round < MAX_ANALYZE_ROUNDS:
                    resp = await self._client.chat.completions.create(
                        model=self._model, messages=messages, temperature=temperature, max_tokens=max_tokens,
                    )
                    choice = resp.choices[0]
                    _current_content = choice.message.content or ""
                    _has_tool_calls = (
                        choice.message.tool_calls
                        or "<invoke" in _current_content
                        or "DSML" in _current_content
                        or "<tool_calls" in _current_content
                    )

            # 尝试 JSON 解析最终内容（剥离任何残留 tool call）
            if any(m in _current_content for m in ["<invoke", "DSML", "<tool_calls"]):
                import re as _clean_re
                for _pat in (
                    r'<[^>]*DSML[^>]*>.*?</[^>]*DSML[^>]*>',
                    r'<invoke[^>]*>.*?</invoke>',
                    r'<tool_calls[^>]*>.*?</tool_calls>',
                ):
                    _current_content = _clean_re.sub(_pat, '', _current_content, flags=_clean_re.DOTALL)
                _current_content = _current_content.strip()
            return _parse_json_safe(_current_content)

        # 无工具模式：直接请求 JSON
        messages.append({"role": "user", "content": "以 JSON 格式回复。"})
        text = await self.chat(messages=messages, temperature=temperature, max_tokens=max_tokens)
        return _parse_json_safe(text)


# ── Helper: Bing web search ──────────────────────────────────────────


async def _do_bing_search(query: str, _re_module) -> str:
    """Execute a Bing search and return formatted result string."""
    try:
        import httpx
        _headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as _client:
            _resp = await _client.get(
                "https://cn.bing.com/search",
                params={"q": query, "setlang": "zh-cn"},
                headers=_headers,
            )
            _titles = _re_module.findall(
                r'<li[^>]*class="b_algo"[^>]*>.*?<a[^>]*href="[^"]*"[^>]*>(.*?)</a>',
                _resp.text, _re_module.DOTALL,
            )
            _found = []
            for _t in _titles[:5]:
                _found.append(_re_module.sub(r"<[^>]+>", "", _t).strip())
            if _found:
                return f"搜索结果({query}): " + "; ".join(_found)
    except Exception:
        pass
    return ""


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
