"""AI chat service — session management, context injection, streaming."""

import json
import logging
import uuid
from collections.abc import AsyncGenerator
from datetime import date, datetime, timedelta

from openai import AsyncOpenAI

from app.ai.prompts import CHAT_SYSTEM
from app.integrations.akshare.fund_datasource import FundDataSource
from app.repositories.fund_repo import FundNavRepo, FundRepo
from app.repositories.news_repo import NewsArticleRepo
from app.repositories.sector_repo import SectorRepo, SectorSnapshotRepo
from app.repositories.system_repo import AIProviderRepo, PromptSettingRepo
from app.repositories.watchlist_repo import WatchedFundRepo

logger = logging.getLogger(__name__)

# ── In-memory session store ────────────────────────────────────────────

Sessions = dict[str, list[dict]]  # session_id → messages
_sessions: Sessions = {}

# System prompt key for DB override
CHAT_SYSTEM_KEY = "chat_system"

# Tool definitions for function calling
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_news",
            "description": "搜索新闻文章，按关键词匹配标题和内容",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {
                        "type": "string",
                        "description": "搜索关键词，如基金名称、板块名称等",
                    },
                    "page_size": {
                        "type": "integer",
                        "description": "返回数量，默认 5",
                    },
                },
                "required": ["keyword"],
            },
        },
    },
]


async def _format_context(context_data: dict) -> str:
    """格式化上下文数据为可读文本."""
    parts = []

    if context_data.get("fund"):
        f = context_data["fund"]
        lines = [
            "## 基金信息",
            f"- 代码：{f.get('code', 'N/A')}",
            f"- 名称：{f.get('name', 'N/A')}",
            f"- 类型：{f.get('type', '未知')}",
            f"- 基金公司：{f.get('company', '未知')}",
            f"- 成立日期：{f.get('established_date', '未知')}",
            f"- 规模：{f.get('scale', '未知')} 亿份",
            f"- 基金经理：{f.get('fund_manager', '未知')}",
        ]
        if f.get("latest_price") is not None:
            lines.append(f"- 最新价：{f['latest_price']}")
        if f.get("latest_change_pct") is not None:
            lines.append(f"- 涨跌幅：{f['latest_change_pct']:+.2f}%")
        parts.append("\n".join(lines))

    if context_data.get("nav_history"):
        lines = ["", "## 近期净值"]
        for n in context_data["nav_history"][:10]:
            lines.append(f"- {n['date']}: {n['nav']:.4f}" + (f" (累计 {n['accumulated_nav']:.4f})" if n.get("accumulated_nav") else ""))
        parts.append("\n".join(lines))

    if context_data.get("estimate"):
        e = context_data["estimate"]
        parts.append(f"\n## 实时估值\n- 估值：{e.get('estimate_nav', 'N/A')}\n- 估算涨跌：{e.get('estimate_change_pct', 'N/A')}")

    if context_data.get("sector"):
        s = context_data["sector"]
        lines = ["", "## 板块信息", f"- 名称：{s.get('name', 'N/A')}", f"- 分类：{s.get('category', 'N/A')}"]
        if s.get("change_pct") is not None:
            lines.append(f"- 涨跌幅：{s['change_pct']:+.2f}%")
        if s.get("price") is not None:
            lines.append(f"- 最新价：{s['price']}")
        parts.append("\n".join(lines))

    if context_data.get("news"):
        lines = ["", "## 相关新闻"]
        for n in context_data["news"]:
            lines.append(f"- {n.get('title', 'N/A')}（{n.get('published_at', '')}）")
        parts.append("\n".join(lines))

    if context_data.get("holding_amount") is not None:
        parts.append(f"\n## 持仓金额\n{context_data['holding_amount']:.2f} 元")

    return "\n".join(parts)


class ChatService:
    """AI 问询服务."""

    def __init__(
        self,
        ai_provider_repo: AIProviderRepo,
        prompt_repo: PromptSettingRepo,
        fund_repo: FundRepo,
        fund_nav_repo: FundNavRepo,
        sector_repo: SectorRepo,
        sector_snapshot_repo: SectorSnapshotRepo,
        news_repo: NewsArticleRepo,
        watchlist_repo: WatchedFundRepo,
    ) -> None:
        self._ai_provider_repo = ai_provider_repo
        self._prompt_repo = prompt_repo
        self._fund_repo = fund_repo
        self._nav_repo = fund_nav_repo
        self._sector_repo = sector_repo
        self._snapshot_repo = sector_snapshot_repo
        self._news_repo = news_repo
        self._watchlist_repo = watchlist_repo
        self._fund_ds = FundDataSource()

    async def _get_system_prompt(self) -> str:
        stored = await self._prompt_repo.get_all()
        return stored.get(CHAT_SYSTEM_KEY) or CHAT_SYSTEM

    async def _gather_context(self, ctx) -> dict:
        """收集页面上下文数据."""
        data: dict = {}

        if ctx.fund_code:
            fund = await self._fund_repo.get_by_code(ctx.fund_code)
            if fund:
                data["fund"] = {
                    "code": fund.code,
                    "name": fund.name,
                    "type": fund.type,
                    "company": fund.company,
                    "established_date": str(fund.established_date) if fund.established_date else None,
                    "scale": float(fund.scale) if fund.scale else None,
                    "fund_manager": fund.fund_manager,
                    "latest_price": float(fund.latest_price) if fund.latest_price else None,
                    "latest_change_pct": float(fund.latest_change_pct) if fund.latest_change_pct else None,
                }

                # NAV history
                navs = await self._nav_repo.get_by_fund_and_date_range(fund.id)
                data["nav_history"] = [
                    {"date": str(n.date), "nav": float(n.nav) if n.nav else 0,
                     "accumulated_nav": float(n.accumulated_nav) if n.accumulated_nav else None}
                    for n in navs[:10]
                ]

                # Live estimate
                try:
                    est = await self._fund_ds.fetch_estimate_by_code(fund.code)
                    if est:
                        data["estimate"] = {
                            "estimate_nav": est.get("estimate_nav"),
                            "estimate_change_pct": est.get("estimate_change_pct"),
                        }
                except Exception:
                    pass

                # Holding amount
                wf = await self._watchlist_repo.get_by_fund_id(fund.id)
                if wf and wf.holding_amount is not None:
                    data["holding_amount"] = float(wf.holding_amount)

                # Related news (by fund name)
                items, _ = await self._news_repo.search(keyword=fund.name, page=1, page_size=5)
                if items:
                    data["news"] = [
                        {"title": n.title, "published_at": str(n.published_at.date()) if n.published_at else ""}
                        for n in items
                    ]

        if ctx.sector_id or ctx.sector_name:
            sector = None
            if ctx.sector_id:
                sector = await self._sector_repo.get(ctx.sector_id)
            elif ctx.sector_name:
                all_ = await self._sector_repo.get_all_active()
                for s in all_:
                    if s.name == ctx.sector_name:
                        sector = s
                        break
            if sector:
                snap = await self._snapshot_repo.get_latest_by_sector(sector.id)
                data["sector"] = {
                    "name": sector.name,
                    "category": sector.category,
                    "price": float(snap.price) if snap and snap.price else None,
                    "change_pct": float(snap.change_pct) if snap and snap.change_pct else None,
                    "volume": float(snap.volume) if snap and snap.volume else None,
                    "turnover": float(snap.turnover) if snap and snap.turnover else None,
                }
                if not data.get("news"):
                    items, _ = await self._news_repo.search(keyword=sector.name, page=1, page_size=5)
                    if items:
                        data["news"] = [
                            {"title": n.title, "published_at": str(n.published_at.date()) if n.published_at else ""}
                            for n in items
                        ]

        return data

    async def chat_stream(
        self,
        session_id: str | None,
        message: str,
        context,
    ) -> AsyncGenerator[str, None]:
        """Handle a chat message and yield SSE events."""
        # Create or resume session
        sid = session_id or uuid.uuid4().hex
        if sid not in _sessions:
            _sessions[sid] = []

        # Gather context
        context_data = await self._gather_context(context)

        # Build system prompt
        system_text = await self._get_system_prompt()
        context_text = await _format_context(context_data)
        system_prompt = f"{system_text}\n\n## 当前页面数据\n{context_text}"

        # Get AI provider
        provider_model = await self._ai_provider_repo.get_active()
        if provider_model is None:
            yield f"data: {json.dumps({'type': 'error', 'content': '未配置 AI 提供者'})}\n\n"
            return

        client = AsyncOpenAI(
            base_url=provider_model.api_base_url,
            api_key=provider_model.api_key,
        )

        # Build messages
        messages: list[dict] = [{"role": "system", "content": system_prompt}]
        for m in _sessions[sid][-20:]:
            msg = dict(m)  # 拷贝避免修改 session 原始数据
            # DeepSeek 思考模式要求所有 assistant 消息必须含 reasoning_content
            if msg["role"] == "assistant" and "reasoning_content" not in msg:
                msg["reasoning_content"] = ""
            messages.append(msg)
        messages.append({"role": "user", "content": message})

        # Prepare tools (conditionally include web search)
        tools = list(TOOLS)
        if context.web_search:
            tools.append({
                "type": "function",
                "function": {
                    "name": "web_search",
                    "description": "搜索互联网获取最新信息",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "搜索关键词"},
                        },
                        "required": ["query"],
                    },
                },
            })

        try:
            stream = await client.chat.completions.create(
                model=provider_model.model_name,
                messages=messages,  # type: ignore[arg-type]
                temperature=0.3,
                max_tokens=4096,
                tools=tools if tools else None,
                stream=True,
                stream_options={"include_usage": False},
            )

            full_content = ""
            full_reasoning = ""
            tool_calls: dict[int, dict] = {}

            async for chunk in stream:
                delta = chunk.choices[0].delta if chunk.choices else None
                if delta is None:
                    continue

                # DeepSeek 思考模式: reasoning_content 通过 model_extra 获取（非标准 OpenAI 字段）
                rc = delta.model_extra.get("reasoning_content") if delta.model_extra else None
                if rc:
                    full_reasoning += rc
                    continue

                # Tool call
                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        idx = tc.index
                        if idx not in tool_calls:
                            tool_calls[idx] = {"id": tc.id, "name": "", "args": ""}
                        if tc.function.name:
                            tool_calls[idx]["name"] = tc.function.name
                        if tc.function.arguments:
                            tool_calls[idx]["args"] += tc.function.arguments
                    continue

                # Text content
                if delta.content:
                    full_content += delta.content
                    yield f"data: {json.dumps({'type': 'token', 'content': delta.content})}\n\n"

            # Handle tool calls
            if tool_calls:
                # Build assistant message with tool_calls (required by OpenAI API)
                assistant_tc = []
                for idx, tc in tool_calls.items():
                    tc_id = tc["id"] or f"call_{idx}"
                    assistant_tc.append({
                        "id": tc_id,
                        "type": "function",
                        "function": {
                            "name": tc["name"],
                            "arguments": tc["args"],
                        },
                    })
                assistant_msg = {
                    "role": "assistant",
                    "content": full_content or None,
                    "tool_calls": assistant_tc,
                    "reasoning_content": full_reasoning or "",
                }
                messages.append(assistant_msg)

                # Execute tools and append tool results
                for idx, tc in tool_calls.items():
                    try:
                        args = json.loads(tc["args"]) if tc["args"] else {}
                    except json.JSONDecodeError:
                        args = {}
                    result = await self._execute_tool(tc["name"], args)
                    yield f"data: {json.dumps({'type': 'tool_result', 'content': result})}\n\n"
                    tc_id = tc["id"] or f"call_{idx}"
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc_id,
                        "content": json.dumps(result, ensure_ascii=False),
                    })

                # Second round: send tool results back to AI

                stream2 = await client.chat.completions.create(
                    model=provider_model.model_name,
                    messages=messages,
                    temperature=0.3,
                    max_tokens=4096,
                    stream=True,
                    stream_options={"include_usage": False},
                )

                round2_content = ""
                round2_reasoning = ""
                async for chunk in stream2:
                    delta = chunk.choices[0].delta if chunk.choices else None
                    if delta is None:
                        continue
                    rc = delta.model_extra.get("reasoning_content") if delta.model_extra else None
                    if rc:
                        round2_reasoning += rc
                        continue
                    if delta.content:
                        round2_content += delta.content
                        yield f"data: {json.dumps({'type': 'token', 'content': delta.content})}\n\n"

                full_content = round2_content
                full_reasoning = round2_reasoning

            # Save to session memory（含 reasoning_content 以兼容 DeepSeek 思考模式）
            assistant_msg: dict = {"role": "assistant", "content": full_content}
            if full_reasoning:
                assistant_msg["reasoning_content"] = full_reasoning
            _sessions[sid].append({"role": "user", "content": message})
            _sessions[sid].append(assistant_msg)

            # Yield session_id for first message
            if session_id is None:
                yield f"data: {json.dumps({'type': 'session_id', 'content': sid})}\n\n"

            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        except Exception as e:
            logger.exception("Chat stream error")
            yield f"data: {json.dumps({'type': 'error', 'content': f'请求失败：{e}'})}\n\n"

    async def _execute_tool(self, name: str, args: dict) -> dict:
        """Execute a tool call and return results."""
        if name == "search_news":
            keyword = args.get("keyword", "")
            page_size = args.get("page_size", 5)
            items, total = await self._news_repo.search(keyword=keyword, page=page_size, page_size=page_size)
            return {
                "total": total,
                "items": [
                    {"title": n.title, "source": n.source, "published_at": str(n.published_at.date()) if n.published_at else "",
                     "content": (n.content or "")[:300]}
                    for n in items
                ],
            }
        elif name == "web_search":
            return {"info": "联网搜索功能未启用"}
        return {"info": "未知工具"}

    @staticmethod
    def destroy_session(session_id: str) -> None:
        _sessions.pop(session_id, None)
