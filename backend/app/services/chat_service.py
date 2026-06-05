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

    if context_data.get("holding_shares") is not None:
        parts.append(f"\n## 持仓份额\n{context_data['holding_shares']:.2f} 份")

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
                if wf and wf.holding_shares is not None:
                    data["holding_shares"] = float(wf.holding_shares)

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
            in_xml_call = False
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
                    # DeepSeek 工具调用检测（支持普通 XML 和 ｜DSML｜ 两种格式）
                    _is_xml = False
                    for _marker in ["<invoke", "DSML", "<tool_calls"]:
                        if _marker in full_content:
                            _is_xml = True
                            break
                    if _is_xml:
                        _open_tags = sum(1 for m in ["<invoke", "<|DSML|", "<tool_calls"] if m in full_content)
                        _close_tags = sum(1 for m in ["</invoke", "</|DSML|", "</tool_calls"] if m in full_content)
                        if _open_tags != _close_tags or any(m in delta.content for m in ["</invoke", "DSML", "<tool_calls", "<invoke"]):
                            continue
                    yield f"data: {json.dumps({'type': 'token', 'content': delta.content})}\n\n"

            # 检查 DeepSeek XML 格式 tool call
            if not tool_calls and "<invoke" in full_content:
                import re as _re
                for _m in _re.finditer(
                    r'<invoke name="(\w+)">(?:\s*<parameter[^>]*>\s*(.*?)\s*</parameter>)?\s*</invoke>',
                    full_content, _re.DOTALL,
                ):
                    idx = len(tool_calls)
                    fn = _m.group(1)
                    param_content = _m.group(2) or ""
                    # 解析参数
                    params = {}
                    for _p in _re.finditer(r'<parameter name="(\w+)"[^>]*>\s*(.*?)\s*</parameter>', param_content, _re.DOTALL):
                        params[_p.group(1)] = _p.group(2)
                    args_str = json.dumps(params) if params else "{}"
                    tool_calls[idx] = {"id": f"xml_call_{idx}", "name": fn, "args": args_str}

            # 多轮 Tool Call 循环（支持 DeepSeek 连续多次调用工具）
            MAX_AI_ROUNDS = 3  # 总轮数上限（首次 + 最多 2 次 follow-up）
            _round = 0

            while tool_calls:
                _round += 1

                # 构建 assistant 消息（含 tool_calls）
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

                # 执行工具并 yield tool_result 事件
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

                # 追加强制指令：告知 AI 已有搜索结果，禁止继续搜索
                messages.append({
                    "role": "user",
                    "content": "基于以上搜索结果直接回答我的问题，不要再调用搜索工具。",
                })

                # 已达最大轮次 → 不再请求 AI，清空内容退出
                if _round >= MAX_AI_ROUNDS:
                    full_content = ""
                    full_reasoning = ""
                    break

                # 将工具结果发回 AI 获取下一轮响应
                stream_n = await client.chat.completions.create(
                    model=provider_model.model_name,
                    messages=messages,
                    temperature=0.3,
                    max_tokens=4096,
                    stream=True,
                    stream_options={"include_usage": False},
                )

                full_content = ""
                full_reasoning = ""
                next_tool_calls: dict[int, dict] = {}

                async for chunk in stream_n:
                    delta = chunk.choices[0].delta if chunk.choices else None
                    if delta is None:
                        continue

                    # DeepSeek 思考模式
                    rc = delta.model_extra.get("reasoning_content") if delta.model_extra else None
                    if rc:
                        full_reasoning += rc
                        continue

                    # 标准 tool_calls（本轮 AI 可能继续调用工具）
                    if delta.tool_calls:
                        for tc in delta.tool_calls:
                            idx = tc.index
                            if idx not in next_tool_calls:
                                next_tool_calls[idx] = {"id": tc.id, "name": "", "args": ""}
                            if tc.function.name:
                                next_tool_calls[idx]["name"] = tc.function.name
                            if tc.function.arguments:
                                next_tool_calls[idx]["args"] += tc.function.arguments
                        continue

                    # 文本内容（含 XML/DSML 检测，抑制 tool call 文本泄漏）
                    if delta.content:
                        full_content += delta.content
                        _is_xml = False
                        for _marker in ["<invoke", "DSML", "<tool_calls"]:
                            if _marker in full_content:
                                _is_xml = True
                                break
                        if _is_xml:
                            _open_tags = sum(1 for m in ["<invoke", "<|DSML|", "<tool_calls"] if m in full_content)
                            _close_tags = sum(1 for m in ["</invoke", "</|DSML|", "</tool_calls"] if m in full_content)
                            if _open_tags != _close_tags or any(m in delta.content for m in ["</invoke", "DSML", "<tool_calls", "<invoke"]):
                                continue

                # 检查本轮内容中是否含 XML/DSML 格式 tool call（无 delta.tool_calls 时的后备检测）
                if not next_tool_calls:
                    import re as _re_xml
                    # 标准 XML 格式
                    for _m in _re_xml.finditer(
                        r'<invoke name="(\w+)">(?:\s*<parameter[^>]*>\s*(.*?)\s*</parameter>)?\s*</invoke>',
                        full_content, _re_xml.DOTALL,
                    ):
                        idx = len(next_tool_calls)
                        fn = _m.group(1)
                        param_content = _m.group(2) or ""
                        params = {}
                        for _p in _re_xml.finditer(
                            r'<parameter name="(\w+)"[^>]*>\s*(.*?)\s*</parameter>',
                            param_content, _re_xml.DOTALL,
                        ):
                            params[_p.group(1)] = _p.group(2)
                        args_str = json.dumps(params) if params else "{}"
                        next_tool_calls[idx] = {"id": f"xml_call_{idx}", "name": fn, "args": args_str}
                    # ｜DSML｜ 格式
                    if not next_tool_calls and "DSML" in full_content:
                        for _m in _re_xml.finditer(
                            r'<｜DSML｜invoke[^>]*name="(\w+)"[^>]*>(.*?)</｜DSML｜invoke>',
                            full_content, _re_xml.DOTALL,
                        ):
                            idx = len(next_tool_calls)
                            fn = _m.group(1)
                            param_text = _m.group(2) or ""
                            params = {}
                            for _p in _re_xml.finditer(
                                r'<parameter[^>]*name="(\w+)"[^>]*>\s*(.*?)\s*</parameter>',
                                param_text, _re_xml.DOTALL,
                            ):
                                params[_p.group(1)] = _p.group(2)
                            args_str = json.dumps(params) if params else "{}"
                            next_tool_calls[idx] = {"id": f"dsml_call_{idx}", "name": fn, "args": args_str}

                tool_calls = next_tool_calls  # 还有 tool call → 继续循环

            logger.debug(
                "Chat tool loop finished. rounds=%d, content_len=%d, tool_calls=%d, reasoning_len=%d",
                _round, len(full_content or ""), len(tool_calls), len(full_reasoning or ""),
            )

            # 剥离 final full_content 中的残留 tool call（支持 XML 和 ｜DSML｜ 格式）
            if any(m in (full_content or "") for m in ["<invoke", "DSML"]):
                import re as _re_final
                full_content = _re_final.sub(r'<[^>]*DSML[^>]*>.*?</[^>]*DSML[^>]*>', '', full_content or "", flags=_re_final.DOTALL)
                full_content = _re_final.sub(r'<invoke[^>]*>.*?</invoke>', '', full_content, flags=_re_final.DOTALL)
                full_content = full_content.strip()

            # 所有轮次都没产生可用文本 → 兜底提示
            if not full_content and _round > 0:
                full_content = "联网搜索暂不可用，请关闭联网搜索重试或稍后重试。"

            # 逐字 yield 最终内容
            if full_content:
                for _i in range(0, len(full_content), 10):
                    yield f"data: {json.dumps({'type': 'token', 'content': full_content[_i:_i+10]})}\n\n"

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
            query = args.get("query", "")
            if not query:
                return {"info": "请提供搜索关键词"}
            try:
                import httpx, re as _re
                headers = {
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                    "Accept-Language": "zh-CN,zh;q=0.9",
                    "Accept": "text/html,application/xhtml+xml",
                }
                async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                    resp = await client.get(
                        "https://cn.bing.com/search",
                        params={"q": query, "setlang": "zh-cn"},
                        headers=headers,
                    )
                    results = []
                    # Bing 搜索结果在 <li class="b_algo"> 中
                    for block in _re.finditer(
                        r'<li[^>]*class="b_algo"[^>]*>(.*?)</li>',
                        resp.text, _re.DOTALL,
                    ):
                        inner = block.group(1)
                        link_m = _re.search(
                            r'<a[^>]*href="(https?://[^"]+)"[^>]*>(.*?)</a>',
                            inner, _re.DOTALL,
                        )
                        if not link_m:
                            continue
                        title = _re.sub(r"<[^>]+>|&[a-z]+;", "", link_m.group(2)).strip()
                        url = link_m.group(1)
                        # 提取摘要（<p> 标签内容）
                        snippet = ""
                        snip_m = _re.search(r'<p[^>]*>(.*?)</p>', inner, _re.DOTALL)
                        if snip_m:
                            snippet = _re.sub(r"<[^>]+>|&[a-z]+;", "", snip_m.group(1)).strip()
                        if title:
                            results.append({"title": title, "url": url, "snippet": snippet})
                        if len(results) >= 8:
                            break
                    if results:
                        # 同时返回结构化结果和纯文本摘要（方便 AI 直接使用）
                        text_parts = [f"搜索结果（{query}）："]
                        for r in results:
                            line = r["title"]
                            if r.get("snippet"):
                                line += f"：{r['snippet']}"
                            text_parts.append(line)
                        return {"results": results, "text_summary": "\n".join(text_parts), "query": query}
                    # 无结果 → 检查是否被限流
                    if resp.status_code == 429 or "captcha" in resp.text[:500].lower():
                        return {"error": "SEARCH_BLOCKED", "message": "搜索服务暂时受限", "query": query}
                    snippet = _re.sub(r"<[^>]+>", " ", resp.text)[:2000]
                    return {"raw_snippet": snippet, "query": query}
            except Exception as e:
                logger.exception("web_search failed")
                return {"info": f"搜索失败: {str(e)[:100]}"}
        return {"info": "未知工具"}

    @staticmethod
    def destroy_session(session_id: str) -> None:
        _sessions.pop(session_id, None)
