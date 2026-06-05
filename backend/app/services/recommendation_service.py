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
    RECOMMEND_FUND_DEFENSIVE,
    RECOMMEND_FUND_LATENT,
    RECOMMEND_FUND_MOMENTUM,
    RECOMMEND_FUND_REBOUND,
    RECOMMEND_SECTOR_DEFENSIVE,
    RECOMMEND_SECTOR_LATENT,
    RECOMMEND_SECTOR_MOMENTUM,
    RECOMMEND_SECTOR_REBOUND,
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
        """获取板块排行摘要（涨幅靠前 + 温和上涨两组）. """
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
            # 获取 limit*2 条，拆为涨幅靠前 + 温和上涨
            rank = await svc.get_rank(
                session=self._sector_repo.session,
                category=cat, limit=limit * 2, sort_by="realtime_change_pct",
            )
            all_items = rank.items[:limit * 2]
            top = [i for i in all_items[:limit] if (i.realtime_change_pct or 0) > 0]
            mild = [i for i in all_items[limit:] if (i.realtime_change_pct or 0) > 0]

            def _fmt(items, start=1):
                buf = []
                for idx, item in enumerate(items, start):
                    name = item.sector_name
                    rt = item.realtime_change_pct or item.change_pct or "-"
                    buf.append(f"  {idx}. {name} 实时涨跌={rt}")
                return buf

            if top:
                lines.append(f"【{cat}板块 | 涨幅靠前】")
                lines.extend(_fmt(top))
            if mild:
                lines.append(f"【{cat}板块 | 温和上涨】")
                lines.extend(_fmt(mild[:limit // 2]))
        return "\n".join(lines) if lines else "（暂无板块数据）"

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
        """获取基金排行摘要（涨幅靠前 + 温和上涨两组）. """
        items, _ = await self._fund_repo.search(
            sort_by="estimate_change_pct", sort_order="desc",
            page=1, page_size=limit * 2,
        )
        all_items = list(items)[:limit * 2]
        top = [i for i in all_items[:limit] if getattr(i, "estimate_change_pct", None) is not None and float(i.estimate_change_pct) > 0]
        mild = [i for i in all_items[limit:] if getattr(i, "estimate_change_pct", None) is not None and float(i.estimate_change_pct) > 0]

        def _fmt(items, start=1):
            buf = []
            for idx, item in enumerate(items, start):
                est = f"{float(item.estimate_change_pct):.2f}%" if getattr(item, "estimate_change_pct", None) is not None else "-"
                buf.append(f"  {idx}. {item.code} {item.name}: 估算涨跌={est}")
            return buf

        lines = []
        if top:
            lines.append("【基金 | 涨幅靠前】")
            lines.extend(_fmt(top))
        if mild:
            lines.append("【基金 | 温和上涨】")
            lines.extend(_fmt(mild[:limit // 2]))
        return "\n".join(lines) if lines else "（暂无基金数据）"

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
    ) -> tuple[list[dict], list[dict]]:
        """筛选符合加仓条件的基金. 返回 (大幅回撤标的, 小幅下跌标的)."""
        from datetime import date as date_type

        today = date_type.today()
        start_20d = today - timedelta(days=25)

        funds, _ = await self._fund_repo.search(page=1, page_size=200)

        big_decliners: list[dict] = []
        mild_decliners: list[dict] = []

        for fund in funds:
            nav_records = await self._fund_nav_repo.get_by_fund_and_date_range(
                fund.id, start=start_20d, end=today,
            )
            if len(nav_records) < 2:
                continue

            sorted_navs = sorted(nav_records, key=lambda x: x.date)

            # 计算阶段跌幅
            first = sorted_navs[0]
            last = sorted_navs[-1]
            if not (first.nav and last.nav and float(first.nav) > 0):
                continue
            drop_pct = (float(last.nav) - float(first.nav)) / float(first.nav) * 100

            # 连续下跌天数
            consecutive_down = 0
            for r in reversed(sorted_navs):
                pct = r.daily_change_pct
                if pct is not None and float(pct) < 0:
                    consecutive_down += 1
                else:
                    break

            # 判断归属组别后再获取实时估值（避免对全部200只都发起网络请求）
            is_big = drop_pct <= -max_drawdown and consecutive_down >= min_consecutive_days
            is_mild = -max_drawdown < drop_pct < 0
            if not is_big and not is_mild:
                continue

            # 实时估值（仅对候选基金执行）
            est = await self._fund_ds.fetch_estimate_by_code(fund.code) if hasattr(self, '_fund_ds') else None
            est_pct = None
            if est and isinstance(est, dict):
                try: est_pct = float(est.get("estimate_change_pct", 0))
                except: pass

            item = {
                "fund_id": str(fund.id),
                "code": fund.code,
                "name": fund.name,
                "type": fund.type or "",
                "drop_pct": round(drop_pct, 2),
                "consecutive_down": consecutive_down,
                "latest_nav": float(last.nav) if last.nav else None,
                "latest_date": str(last.date) if last.date else "",
                "estimate_change_pct": est_pct,
            }

            if is_big:
                big_decliners.append(item)
                if len(big_decliners) >= limit:
                    break
            else:
                mild_decliners.append(item)

        return big_decliners, mild_decliners

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

    # ── 提示词 key 映射（category × mode） ─────────────────────────────────
    _PROMPT_KEYS: dict[str, dict[str, tuple[str, str]]] = {
        "fund": {
            "momentum": ("recommend_fund_momentum", "recommend_fund_user"),
            "latent": ("recommend_fund_latent", "recommend_fund_user"),
            "rebound": ("recommend_fund_rebound", "recommend_fund_user"),
            "defensive": ("recommend_fund_defensive", "recommend_fund_user"),
        },
        "sector": {
            "momentum": ("recommend_sector_momentum", "recommend_sector_user"),
            "latent": ("recommend_sector_latent", "recommend_sector_user"),
            "rebound": ("recommend_sector_rebound", "recommend_sector_user"),
            "defensive": ("recommend_sector_defensive", "recommend_sector_user"),
        },
    }
    _PROMPT_DEFAULTS: dict[str, dict[str, str]] = {
        "fund": {
            "momentum": RECOMMEND_FUND_MOMENTUM,
            "latent": RECOMMEND_FUND_LATENT,
            "rebound": RECOMMEND_FUND_REBOUND,
            "defensive": RECOMMEND_FUND_DEFENSIVE,
        },
        "sector": {
            "momentum": RECOMMEND_SECTOR_MOMENTUM,
            "latent": RECOMMEND_SECTOR_LATENT,
            "rebound": RECOMMEND_SECTOR_REBOUND,
            "defensive": RECOMMEND_SECTOR_DEFENSIVE,
        },
    }

    async def generate(
        self, category: str, mode: str, limit: int = 10,
    ) -> list[RecommendItem]:
        """按类别+子策略生成推荐。category=fund|sector, mode=momentum|latent|rebound|defensive."""
        ai = await self._get_provider()

        # 选提示词
        sys_key, usr_key = self._PROMPT_KEYS[category][mode]
        sys_default = self._PROMPT_DEFAULTS[category][mode]
        system = await self._get_prompt(sys_key, sys_default)
        user_template = await self._get_prompt(usr_key, RECOMMEND_TOP_PICKS_USER)

        # 收集数据
        news = await self._get_news_sentiment_summary()
        money_flow = await self._get_money_flow_data(limit)

        if category == "fund":
            if mode in ("momentum",):
                sector_rank = "（仅分析基金，不提供板块数据）"
                fund_rank = await self._get_fund_rank_data(limit)
            elif mode == "latent":
                sector_rank = "（仅分析基金，不提供板块数据）"
                fund_rank = await self._get_fund_rank_data(limit)
            else:
                # rebound / defensive: 使用 dip_candidates 数据
                sector_rank = "（仅分析基金，不提供板块数据）"
                big_d, mild_d = await self._get_dip_candidates(
                    max_drawdown=5.0, min_consecutive_days=3, limit=limit,
                )
                targets = big_d if mode == "rebound" else mild_d
                lines = []
                for c in targets:
                    est = f" 实时估值涨跌={c['estimate_change_pct']:+.2f}%" if c.get('estimate_change_pct') is not None else ""
                    lines.append(f"{c['code']} {c['name']}: 阶段跌幅={c['drop_pct']}% 连跌={c['consecutive_down']}天{est}")
                fund_rank = "\n".join(lines) if lines else "（暂无基金数据）"
        else:
            # sector
            full_rank = await self._get_sector_rank_data(limit * 2)
            fund_rank = "（仅分析板块，不提供基金数据）"
            sector_rank = full_rank

        user = user_template.format(
            category=f"{'基金' if category == 'fund' else '板块'}",
            limit=limit,
            sector_rank=sector_rank or "（暂无数据）",
            money_flow=money_flow or "（暂无数据）",
            fund_rank=fund_rank or "（暂无数据）",
            news_sentiment=news or "（暂无数据）",
        )

        try:
            result = await ai.analyze(
                system_prompt=system, user_prompt=user,
                max_tokens=8192,
                tools=self._web_search_tool,
            )
        except Exception as e:
            logger.exception("AI generate failed: %s/%s", category, mode)
            raise

        raw_items = result.get("recommendations", []) if isinstance(result, dict) else []
        items = []
        for r in raw_items[:limit]:
            try:
                items.append(RecommendItem(
                    type=category,
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
                logger.exception("Skipping invalid generate item")

        await self._save_results(items, mode=mode)
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
