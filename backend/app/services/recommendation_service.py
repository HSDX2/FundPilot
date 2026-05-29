"""推荐服务 — Top Picks 与 Dip Buy 综合推荐."""

import json
import logging
from datetime import date, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select

from app.ai.openai_compat import OpenAICompatibleProvider
from app.ai.prompts import (
    RECOMMEND_DIP_BUY_SYSTEM,
    RECOMMEND_DIP_BUY_USER,
    RECOMMEND_TOP_PICKS_SYSTEM,
    RECOMMEND_TOP_PICKS_USER,
)
from app.integrations.akshare.fund_datasource import FundDataSource
from app.models.analysis import Recommendation
from app.repositories.analysis_repo import RecommendationRepo
from app.repositories.fund_repo import FundNavRepo, FundRepo
from app.repositories.news_repo import NewsArticleRepo
from app.repositories.sector_repo import (
    SectorMoneyFlowRepo,
    SectorRepo,
    SectorSnapshotRepo,
)
from app.repositories.system_repo import AIProviderRepo, PromptSettingRepo
from app.schemas.recommend import RecommendItem

logger = logging.getLogger(__name__)


class RecommendationService:
    """推荐服务 — 综合推荐与加仓推荐."""

    def __init__(
        self,
        ai_provider_repo: AIProviderRepo,
        prompt_setting_repo: PromptSettingRepo,
        fund_repo: FundRepo,
        fund_nav_repo: FundNavRepo,
        sector_repo: SectorRepo,
        sector_snapshot_repo: SectorSnapshotRepo,
        sector_money_flow_repo: SectorMoneyFlowRepo,
        news_repo: NewsArticleRepo,
        recommendation_repo: RecommendationRepo,
        fund_datasource: FundDataSource | None = None,
    ) -> None:
        self._ai_provider_repo = ai_provider_repo
        self._prompt_repo = prompt_setting_repo
        self._fund_repo = fund_repo
        self._fund_nav_repo = fund_nav_repo
        self._sector_repo = sector_repo
        self._snapshot_repo = sector_snapshot_repo
        self._money_flow_repo = sector_money_flow_repo
        self._news_repo = news_repo
        self._rec_repo = recommendation_repo
        self._fund_ds = fund_datasource or FundDataSource()

    _web_search_tool: list[dict] | None = None

    async def _get_provider(self) -> OpenAICompatibleProvider:
        provider = await self._ai_provider_repo.get_active()
        if provider is None:
            raise RuntimeError("No active AI provider configured")

        if getattr(provider, "web_search_enabled", False):
            self._web_search_tool = [{
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
            }]
        else:
            self._web_search_tool = None

        return OpenAICompatibleProvider(
            base_url=provider.api_base_url,
            api_key=provider.api_key,
            model=provider.model_name,
            provider_type=provider.provider_type,
        )

    async def _get_prompt(self, key: str, default: str) -> str:
        stored = await self._prompt_repo.get_all()
        return stored.get(key) or default

    async def _get_sector_rank_data(self, limit: int = 20) -> str:
        """获取板块排行摘要."""
        from app.repositories.sector_repo import (
            SectorRealtimeRepo,
            SectorSnapshotRepo,
        )
        from app.services.sector_service import SectorService

        lines = []
        for cat in ("industry", "concept"):
            svc = SectorService(
                sector_repo=self._sector_repo,
                sector_snapshot_repo=self._snapshot_repo,
                sector_money_flow_repo=self._money_flow_repo,
                sector_realtime_repo=SectorRealtimeRepo(
                    self._sector_repo.session,
                ),
            )
            rank = await svc.get_rank(
                session=self._sector_repo.session,
                category=cat, limit=limit, sort_by="realtime_change_pct",
            )
            lines.append(f"【{cat}板块】")
            for i, item in enumerate(rank.items[:limit], 1):
                name = item.sector_name
                rt = item.realtime_change_pct or item.change_pct or "-"
                lines.append(f"  {i}. {name} 实时涨跌={rt}")
        return "\n".join(lines)

    async def _get_money_flow_data(self, limit: int = 20) -> str:
        """获取资金流向摘要."""
        from app.integrations.akshare.sector_datasource import SectorDataSource

        ds = SectorDataSource()
        try:
            data = await ds.fetch_money_flow_rank(period="today")
        except Exception:
            return "（资金流向数据暂不可用）"

        items = (data or [])[:limit]
        lines = []
        for item in items:
            name = item.get("name", "?")
            inflow = item.get("main_force_net_inflow") or 0
            yiyuan = inflow / 1e8
            lines.append(f"  {name}: 主力净流入 {yiyuan:.2f}亿")
        return "\n".join(lines) if lines else "（暂无资金流向数据）"

    async def _get_fund_rank_data(self, limit: int = 20) -> str:
        """获取基金排行摘要."""
        items, _ = await self._fund_repo.search(
            sort_by="estimate_change_pct", sort_order="desc",
            page=1, page_size=limit,
        )
        lines = []
        for i, item in enumerate(items, 1):
            est = (
                f"{float(item.estimate_change_pct):.2f}%"
                if getattr(item, "estimate_change_pct", None) is not None
                else "-"
            )
            lines.append(f"  {i}. {item.code} {item.name}: 估算涨跌={est}")
        return "\n".join(lines)

    async def _get_news_sentiment_summary(self, limit: int = 10) -> str:
        """获取最新新闻情绪摘要."""
        from datetime import datetime

        items, _ = await self._news_repo.search(
            start=datetime.now() - timedelta(days=3),
            page=1, page_size=limit,
        )
        lines = []
        for item in items:
            score = item.sentiment_score
            tag = f"情绪={score}" if score is not None else "未分析"
            lines.append(f"  [{item.source}] {item.title[:30]}… {tag}")
        return "\n".join(lines) if lines else "（暂无新闻数据）"

    async def _get_dip_candidates(
        self, max_drawdown: float = 5.0, min_consecutive_days: int = 3, limit: int = 20,
    ) -> list[dict]:
        """筛选符合加仓条件的基金."""
        from datetime import date as date_type

        today = date_type.today()
        start_20d = today - timedelta(days=25)

        funds, _ = await self._fund_repo.search(page=1, page_size=200)

        candidates = []
        for fund in funds:
            nav_records = await self._fund_nav_repo.get_by_fund_and_date_range(
                fund.id, start=start_20d, end=today,
            )
            if len(nav_records) < min_consecutive_days + 1:
                continue

            sorted_navs = sorted(nav_records, key=lambda x: x.date)
            latest_pct_values = []
            consecutive_down = 0
            for r in reversed(sorted_navs):
                pct = r.daily_change_pct
                if pct is not None:
                    latest_pct_values.append(float(pct))
                    if float(pct) < 0:
                        consecutive_down += 1
                    else:
                        break

            if consecutive_down < min_consecutive_days:
                continue

            # 计算阶段跌幅
            first = sorted_navs[0]
            last = sorted_navs[-1]
            if first.nav and last.nav and float(first.nav) > 0:
                drop_pct = (float(last.nav) - float(first.nav)) / float(first.nav) * 100
            else:
                continue

            if drop_pct > -max_drawdown:
                continue

            candidates.append({
                "fund_id": str(fund.id),
                "code": fund.code,
                "name": fund.name,
                "type": fund.type or "",
                "drop_pct": round(drop_pct, 2),
                "consecutive_down": consecutive_down,
                "latest_nav": float(last.nav) if last.nav else None,
                "latest_date": str(last.date) if last.date else "",
            })
            if len(candidates) >= limit:
                break

        return candidates

    async def _get_nav_snippets(self, fund_ids: list[str], days: int = 10) -> str:
        """获取指定基金的净值走势片段."""
        lines = []
        for fid in fund_ids:
            fund = await self._fund_repo.get(UUID(fid))
            if not fund:
                continue
            today = date.today()
            navs = await self._fund_nav_repo.get_by_fund_and_date_range(
                UUID(fid), start=today - timedelta(days=days), end=today,
            )
            nav_strs = [
                f"{r.date}: NAV={r.nav}, 涨跌={r.daily_change_pct}"
                for r in sorted(navs, key=lambda x: x.date)
                if r.nav is not None
            ]
            if nav_strs:
                lines.append(f"{fund.code} {fund.name}:")
                for s in nav_strs[-10:]:
                    lines.append(f"  {s}")
        return "\n".join(lines) if lines else "（暂无净值数据）"

    async def _get_sector_performance_for_funds(
        self, fund_names: list[str],
    ) -> str:
        """查询基金相关的板块表现."""
        from app.models.sector import Sector
        from sqlalchemy import select

        result = await self._sector_repo.session.execute(
            select(Sector).limit(30),
        )
        sectors = result.scalars().all()
        lines = []
        for s in sectors[:10]:
            lines.append(f"{s.name}: 分类={s.category}")
        return "\n".join(lines)

    async def top_picks(
        self, limit: int = 10, category: str | None = None,
    ) -> list[RecommendItem]:
        """综合推荐."""
        ai = await self._get_provider()
        system = await self._get_prompt(
            "recommend_top_picks_system", RECOMMEND_TOP_PICKS_SYSTEM,
        )
        user_template = await self._get_prompt(
            "recommend_top_picks_user", RECOMMEND_TOP_PICKS_USER,
        )

        sector_rank = await self._get_sector_rank_data(limit)
        money_flow = await self._get_money_flow_data(limit)
        fund_rank = await self._get_fund_rank_data(limit)
        news = await self._get_news_sentiment_summary()

        user = user_template.format(
            category=category or "基金和板块",
            limit=limit,
            sector_rank=sector_rank or "（暂无数据）",
            money_flow=money_flow or "（暂无数据）",
            fund_rank=fund_rank or "（暂无数据）",
            news_sentiment=news or "（暂无数据）",
        )

        try:
            result = await ai.analyze(
                system_prompt=system, user_prompt=user,
                tools=self._web_search_tool,
            )
        except Exception as e:
            logger.exception("AI top picks analysis failed")
            raise

        raw_items = result.get("recommendations", []) if isinstance(result, dict) else []
        items = []
        for r in raw_items[:limit]:
            try:
                items.append(RecommendItem(
                    type=r.get("type", "fund"),
                    action=r.get("action", "buy"),
                    target_id=r.get("target_code", "") or r.get("target_name", ""),
                    target_name=r.get("target_name", ""),
                    target_code=r.get("target_code"),
                    confidence=int(r.get("confidence", 50)),
                    reason_summary=r.get("reason_summary", ""),
                    reason_detail=r.get("reason_detail"),
                    risk_warning=r.get("risk_warning"),
                ))
            except Exception:
                logger.exception("Skipping invalid recommendation item")

        await self._save_results(items, mode="top_picks")
        return items

    async def dip_buy(
        self, limit: int = 10,
        max_drawdown: float = 5.0,
        min_consecutive_days: int = 3,
    ) -> list[RecommendItem]:
        """加仓推荐."""
        ai = await self._get_provider()
        system = await self._get_prompt(
            "recommend_dip_buy_system", RECOMMEND_DIP_BUY_SYSTEM,
        )
        user_template = await self._get_prompt(
            "recommend_dip_buy_user", RECOMMEND_DIP_BUY_USER,
        )

        candidates = await self._get_dip_candidates(max_drawdown, min_consecutive_days, limit)
        if not candidates:
            return []

        fund_ids = [c["fund_id"] for c in candidates]
        nav_snippets = await self._get_nav_snippets(fund_ids)
        sector_perf = await self._get_sector_performance_for_funds(
            [c["name"] for c in candidates],
        )
        news = await self._get_news_sentiment_summary()

        cand_lines = []
        for c in candidates:
            cand_lines.append(
                f"{c['code']} {c['name']}: "
                f"阶段跌幅={c['drop_pct']}% 连跌={c['consecutive_down']}天 "
                f"最新净值={c['latest_nav']} ({c['latest_date']})",
            )

        user = user_template.format(
            max_drawdown=max_drawdown,
            min_consecutive_days=min_consecutive_days,
            dip_candidates="\n".join(cand_lines),
            nav_snippets=nav_snippets or "（暂无净值数据）",
            sector_performance=sector_perf or "（暂无板块数据）",
            news_sentiment=news or "（暂无新闻数据）",
        )

        try:
            result = await ai.analyze(
                system_prompt=system, user_prompt=user,
                tools=self._web_search_tool,
            )
        except Exception as e:
            logger.exception("AI dip buy analysis failed")
            raise

        raw_items = result.get("recommendations", []) if isinstance(result, dict) else []
        items = []
        for r in raw_items[:limit]:
            try:
                items.append(RecommendItem(
                    type="fund",
                    action=r.get("action", "watch"),
                    target_id=r.get("target_code", "") or r.get("target_name", ""),
                    target_name=r.get("target_name", ""),
                    target_code=r.get("target_code"),
                    confidence=int(r.get("confidence", 50)),
                    reason_summary=r.get("reason_summary", ""),
                    reason_detail=r.get("reason_detail"),
                    risk_warning=r.get("risk_warning"),
                ))
            except Exception:
                logger.exception("Skipping invalid dip buy item")

        # 保存到数据库
        await self._save_results(items, mode="dip_buy")
        return items

    async def _save_results(self, items: list[RecommendItem], mode: str = "top_picks") -> None:
        """将推荐结果持久化到 recommendations 表."""
        today = date.today()

        # 板块名称 → UUID 映射（用于板块推荐跳转）
        from app.models.sector import Sector
        result = await self._sector_repo.session.execute(
            select(Sector.id, Sector.name, Sector.code),
        )
        sector_map = {}
        for row in result:
            sector_map[row.name] = {"id": str(row.id), "code": row.code}

        for item in items:
            code = item.target_code
            if item.type == "sector":
                # 板块用 UUID 做跳转，先精确匹配，再前缀匹配
                match = sector_map.get(item.target_name)
                if match is None:
                    # 前缀匹配：AI 可能返回 "白酒板块" → 匹配 "白酒"
                    for name, m in sector_map.items():
                        if item.target_name.startswith(name) or name.startswith(item.target_name):
                            match = m
                            break
                if match:
                    code = match["id"]
                    item.target_code = match["id"]
                    item.target_id = match["id"]
            rec = Recommendation(
                date=today,
                mode=mode,
                rec_type=item.type,
                action=item.action,
                target_name=item.target_name,
                target_code=code,
                confidence=item.confidence,
                reason_summary=item.reason_summary,
                reason_detail=item.reason_detail,
                risk_warning=item.risk_warning,
            )
            self._rec_repo.session.add(rec)
        await self._rec_repo.session.flush()

    async def list_recent(
        self, page: int = 1, page_size: int = 20,
        start_date: date | None = None, end_date: date | None = None,
        mode: str | None = None,
    ) -> tuple[list[Recommendation], int]:
        """从数据库查询历史推荐记录."""
        return await self._rec_repo.list_recent(
            page=page, page_size=page_size,
            start_date=start_date, end_date=end_date,
            mode=mode,
        )
