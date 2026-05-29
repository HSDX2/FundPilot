"""AI analysis service — sector reports, fund advice, news sentiment."""

import asyncio
import logging
from datetime import date, datetime, timedelta

from app.ai.base import AIProvider
from app.ai.openai_compat import OpenAICompatibleProvider
from app.ai.prompts import (
    FUND_ADVICE_SYSTEM,
    FUND_ADVICE_USER,
    NEWS_SENTIMENT_SYSTEM,
    NEWS_SENTIMENT_USER,
    SECTOR_ANALYSIS_SYSTEM,
    SECTOR_ANALYSIS_USER_DAILY,
    SECTOR_ANALYSIS_USER_MONTHLY,
    SECTOR_ANALYSIS_USER_WEEKLY,
)
from app.integrations.akshare.fund_datasource import FundDataSource
from app.models.analysis import AnalysisReport, FundAdvice
from app.repositories.analysis_repo import AnalysisReportRepo, FundAdviceRepo
from app.repositories.fund_repo import FundEstimateRepo, FundNavRepo, FundRepo
from app.repositories.news_repo import NewsArticleRepo
from app.repositories.sector_repo import (
    SectorMoneyFlowRepo,
    SectorRepo,
    SectorSnapshotRepo,
)
from app.repositories.system_repo import AIProviderRepo, PromptSettingRepo
from app.repositories.watchlist_repo import WatchedFundRepo

logger = logging.getLogger(__name__)

_SECTOR_PROMPT_MAP = {
    "daily": SECTOR_ANALYSIS_USER_DAILY,
    "weekly": SECTOR_ANALYSIS_USER_WEEKLY,
    "monthly": SECTOR_ANALYSIS_USER_MONTHLY,
}


class AnalysisService:
    """AI-powered analysis engine for sectors, funds, and news."""

    def __init__(
        self,
        ai_provider_repo: AIProviderRepo,
        prompt_setting_repo: PromptSettingRepo,
        analysis_report_repo: AnalysisReportRepo,
        fund_advice_repo: FundAdviceRepo,
        sector_repo: SectorRepo,
        sector_snapshot_repo: SectorSnapshotRepo,
        sector_money_flow_repo: SectorMoneyFlowRepo,
        fund_repo: FundRepo,
        fund_nav_repo: FundNavRepo,
        fund_estimate_repo: FundEstimateRepo,
        news_repo: NewsArticleRepo,
        watchlist_repo: WatchedFundRepo,
        fund_datasource: FundDataSource | None = None,
    ) -> None:
        self._ai_provider_repo = ai_provider_repo
        self._prompt_repo = prompt_setting_repo
        self._report_repo = analysis_report_repo
        self._advice_repo = fund_advice_repo
        self._sector_repo = sector_repo
        self._snapshot_repo = sector_snapshot_repo
        self._money_flow_repo = sector_money_flow_repo
        self._fund_repo = fund_repo
        self._nav_repo = fund_nav_repo
        self._est_repo = fund_estimate_repo
        self._news_repo = news_repo
        self._watchlist_repo = watchlist_repo
        self._fund_ds = fund_datasource or FundDataSource()

    async def _get_provider(self) -> AIProvider:
        provider_model = await self._ai_provider_repo.get_active()
        if provider_model is None:
            raise RuntimeError("No active AI provider configured")
        return OpenAICompatibleProvider(
            base_url=provider_model.api_base_url,
            api_key=provider_model.api_key,
            model=provider_model.model_name,
            provider_type=provider_model.provider_type,
        )

    async def _get_system_prompt(self, key: str, default: str) -> str:
        """获取系统提示词：优先使用 DB 自定义版本，否则返回默认值."""
        stored = await self._prompt_repo.get_all()
        return stored.get(key) or default

    async def _get_user_prompt(self, key: str, default: str) -> str:
        """获取用户提示词模板：优先使用 DB 自定义版本，否则返回默认值."""
        stored = await self._prompt_repo.get_all()
        return stored.get(key) or default

    # ── Sector Analysis ───────────────────────────────────────────────

    async def generate_sector_report(
        self,
        sector_id,
        report_type: str = "daily",
    ) -> AnalysisReport:
        ai = await self._get_provider()
        sector = await self._sector_repo.get(sector_id)
        if sector is None:
            raise ValueError(f"Sector {sector_id} not found")

        today = date.today()
        snapshot = await self._snapshot_repo.get_latest_by_sector(sector_id)
        money_flow = await self._money_flow_repo.get_by_sector_and_date(
            sector_id, today,
        )

        # Build recent changes string
        now = datetime.now()
        recent_snapshots = await self._snapshot_repo.get_by_sector_and_time_range(
            sector_id,
            start=now - timedelta(days=7),
            end=now,
        )
        recent_changes = "\n".join(
            f"- {s.timestamp.strftime('%m-%d') if s.timestamp else '??-??'}: "
            f"{s.change_pct:+.2f}%" if s.change_pct is not None else "N/A"
            for s in recent_snapshots[:10]
        ) if recent_snapshots else "暂无近期数据"

        # Build news titles
        news_titles = "暂无相关新闻"
        news_items, _ = await self._news_repo.search(
            keyword=sector.name, page=1, page_size=5,
        )
        if news_items:
            news_titles = "\n".join(
                f"- {n.title}" for n in news_items
            )

        default_user = _SECTOR_PROMPT_MAP.get(
            report_type, SECTOR_ANALYSIS_USER_DAILY
        )
        system_prompt = await self._get_system_prompt(
            "sector_analysis_system", SECTOR_ANALYSIS_SYSTEM,
        )
        user_prompt_template = await self._get_user_prompt(
            f"sector_analysis_user_{report_type}", default_user,
        )
        user_prompt = user_prompt_template.format(
            sector_name=sector.name,
            category=sector.category,
            latest_price=snapshot.price if snapshot else "N/A",
            change_pct=(
                f"{snapshot.change_pct:+.2f}"
                if snapshot and snapshot.change_pct else "N/A"
            ),
            volume=snapshot.volume if snapshot else "N/A",
            turnover=snapshot.turnover if snapshot else "N/A",
            main_force_inflow=(
                f"{money_flow.main_force_net_inflow:+.2f}"
                if money_flow and money_flow.main_force_net_inflow
                else "N/A"
            ),
            super_large_inflow="N/A",
            large_inflow="N/A",
            medium_inflow=(
                f"{money_flow.middle_net_inflow:+.2f}"
                if money_flow and money_flow.middle_net_inflow
                else "N/A"
            ),
            small_inflow=(
                f"{money_flow.retail_net_inflow:+.2f}"
                if money_flow and money_flow.retail_net_inflow
                else "N/A"
            ),
            recent_changes=recent_changes,
            news_titles=news_titles,
            weekly_snapshots=recent_changes,
            weekly_money_flow="N/A",
            monthly_summary=recent_changes,
            monthly_money_flow="N/A",
        )

        result = await ai.analyze(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )

        report = AnalysisReport(
            date=today,
            report_type=report_type,
            category=sector.category,
            sector_id=sector.id,
            content=result,
            ai_model=ai.model,
        )
        self._report_repo.session.add(report)
        await self._report_repo.session.flush()
        return report

    async def generate_all_sector_reports(
        self,
        report_type: str = "daily",
        limit: int = 10,
        sector_ids: list[str] | None = None,
        category: str | None = None,
    ) -> list[AnalysisReport]:
        """Generate reports for top sectors (optionally filtered by category)."""
        from sqlalchemy import func, select

        from app.models.sector import SectorSnapshot

        if sector_ids:
            sectors_to_process = []
            for sid in sector_ids:
                sector = await self._sector_repo.get(sid)
                if sector:
                    sectors_to_process.append(sector)
        else:
            ts_stmt = select(func.max(SectorSnapshot.timestamp))
            ts_result = await self._sector_repo.session.execute(ts_stmt)
            latest_ts = ts_result.scalar()
            if latest_ts is None:
                sectors_to_process = list(await self._sector_repo.get_all_active())[:limit]
            else:
                latest_snapshots = await self._snapshot_repo.get_rank_by_timestamp(
                    timestamp=latest_ts, limit=limit, category=category,
                )
                sectors_to_process = [s for _, s in latest_snapshots]

            # 如果指定了 category 但快照不够，从活跃板块补充
            if category and len(sectors_to_process) < limit:
                active = await self._sector_repo.get_active_by_category(category)
                existing = {s.id for s in sectors_to_process}
                for s in active:
                    if s.id not in existing:
                        sectors_to_process.append(s)
                    if len(sectors_to_process) >= limit:
                        break

        sem = asyncio.Semaphore(3)  # 最多 3 个并发 AI 调用

        async def _generate_one(sector):
            async with sem:
                try:
                    return await self.generate_sector_report(
                        sector.id, report_type,
                    )
                except Exception:
                    logger.exception(
                        "Failed to generate report for sector %s", sector.id,
                    )
                    return None

        results = await asyncio.gather(
            *(_generate_one(s) for s in sectors_to_process),
        )
        return [r for r in results if r is not None]

    # ── Fund Advice ───────────────────────────────────────────────────

    async def _get_fund_sector_performance(self, fund) -> str:
        """查找基金关联的板块及其最新表现."""
        try:
            sectors = await self._sector_repo.get_all_active()
            parts = []
            for s in sectors:
                if not s.name:
                    continue
                # 板块名出现在基金名中，或基金名出现在板块名中
                if s.name in fund.name or fund.name in s.name:
                    snap = await self._snapshot_repo.get_latest_by_sector(s.id)
                    if snap and snap.change_pct is not None:
                        pct = f"{snap.change_pct:+.2f}%"
                    else:
                        pct = "N/A"
                    parts.append(f"{s.name}: {pct}")
            return "\n".join(parts) if parts else "暂无关联板块数据"
        except Exception:
            logger.debug("Failed to lookup sector performance for %s", fund.code)
            return "暂无关联板块数据"

    async def generate_fund_advice(self, fund_id) -> FundAdvice:
        ai = await self._get_provider()
        fund = await self._fund_repo.get(fund_id)
        if fund is None:
            raise ValueError(f"Fund {fund_id} not found")

        today = date.today()

        # Load NAV history (last 10 days)
        navs = await self._nav_repo.get_by_fund_and_date_range(fund_id)
        nav_history = "\n".join(
            f"- {n.date}: 净值 {n.nav:.4f}" + (
                f" (累计 {n.accumulated_nav:.4f})"
                if n.accumulated_nav else ""
            )
            for n in navs[:10]
        ) if navs else "暂无净值数据"

        # Load latest estimate  via live API (not from DB)
        estimate_str = "暂无实时估值"
        try:
            est = await self._fund_ds.fetch_estimate_by_code(fund.code)
            if est and est.get("estimate_nav") is not None:
                est_nav = est.get("estimate_nav")
                est_pct = est.get("estimate_change_pct")
                if est_pct is not None:
                    estimate_str = (
                        f"估值: {est_nav:.4f}, "
                        f"涨跌: {est_pct:+.2f}%"
                    )
                else:
                    estimate_str = f"估值: {est_nav:.4f}"
            elif fund.latest_price is not None:
                # ETF 回退：使用 fund 表 latest_price / latest_change_pct
                pct_str = (
                    f", 涨跌: {float(fund.latest_change_pct):+.2f}%"
                    if fund.latest_change_pct is not None else ""
                )
                estimate_str = f"实时价: {float(fund.latest_price):.4f}{pct_str}"
        except Exception:
            logger.debug("Live estimate fetch failed for %s", fund.code)

        # News
        news_titles = "暂无"
        news_items, _ = await self._news_repo.search(
            keyword=fund.name, page=1, page_size=3,
        )
        if news_items:
            news_titles = "\n".join(f"- {n.title}" for n in news_items)

        system_prompt = await self._get_system_prompt(
            "fund_advice_system", FUND_ADVICE_SYSTEM,
        )
        user_prompt_template = await self._get_user_prompt(
            "fund_advice_user", FUND_ADVICE_USER,
        )
        user_prompt = user_prompt_template.format(
            fund_name=fund.name,
            fund_code=fund.code,
            fund_type=fund.type or "未知",
            latest_nav=navs[0].nav if navs else "N/A",
            accumulated_nav=navs[0].accumulated_nav if navs else "N/A",
            nav_history=nav_history,
            estimate=estimate_str,
            sector_performance=await self._get_fund_sector_performance(fund),
            news_titles=news_titles,
        )

        # 追加持仓金额（取自关注列表）
        holding_amount_str = "未设置"
        wf = await self._watchlist_repo.get_by_fund_id(fund_id)
        if wf and wf.holding_amount is not None:
            holding_amount_str = f"{float(wf.holding_amount):.2f} 元"
        user_prompt += f"\n\n持仓金额：{holding_amount_str}"

        result = await ai.analyze(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )

        action = result.get("action", "hold")
        if action not in ("buy", "hold", "reduce", "redeem"):
            action = "hold"

        confidence_val = result.get("confidence")
        try:
            confidence = float(confidence_val) if confidence_val is not None else None
        except (TypeError, ValueError):
            confidence = None

        advice = FundAdvice(
            fund_id=fund_id,
            date=today,
            action=action,
            reason=result.get("reason", {}),
            confidence=confidence,
            ai_model=ai.model,
        )
        self._advice_repo.session.add(advice)
        await self._advice_repo.session.flush()
        return advice

    async def generate_batch_fund_advice(
        self, fund_ids: list[str],
    ) -> list[FundAdvice]:
        """Generate advice for multiple funds."""
        results = []
        for fid in fund_ids:
            try:
                advice = await self.generate_fund_advice(fid)
                results.append(advice)
            except Exception:
                logger.exception("Failed to generate advice for fund %s", fid)
        return results

    # ── News Sentiment ────────────────────────────────────────────────

    async def analyze_news_sentiment(self, news_id) -> None:
        """Analyze sentiment for a single news article."""
        ai = await self._get_provider()
        news = await self._news_repo.get(news_id)
        if news is None:
            raise ValueError(f"News {news_id} not found")

        content = news.content or news.title or ""
        system_prompt = await self._get_system_prompt(
            "news_sentiment_system", NEWS_SENTIMENT_SYSTEM,
        )
        user_prompt_template = await self._get_user_prompt(
            "news_sentiment_user", NEWS_SENTIMENT_USER,
        )
        user_prompt = user_prompt_template.format(
            title=news.title or "",
            source=news.source or "未知",
            published_at=news.published_at.isoformat() if news.published_at else "未知",
            content=content[:2000],
        )

        result = await ai.analyze(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )

        score_val = result.get("score")
        try:
            news.sentiment_score = float(score_val) if score_val is not None else None
        except (TypeError, ValueError):
            news.sentiment_score = None

        # 保存完整分析结果（除 score 外）
        news.sentiment_detail = {
            k: v for k, v in result.items()
            if k != "score" and v is not None
        }

        # 不在这里 flush——并发分析时多个任务同时 flush 会导致
        # "Session is already flushing" 错误，由外层调用方统一 commit。

    async def batch_analyze_sentiment(
        self,
        limit: int = 20,
        concurrency: int = 3,
        force: bool = False,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> tuple[int, list[str]]:
        """Analyze sentiment for news. Set force=True to re-analyze all."""
        today = date.today()
        if start_date is None:
            start_date = today - timedelta(days=3)
        if end_date is None:
            end_date = today
        news_items, _ = await self._news_repo.search(
            start=datetime.combine(start_date, datetime.min.time()),
            end=datetime.combine(end_date, datetime.max.time()),
            page=1,
            page_size=limit,
            sentiment_null=not force,
        )
        targets = list(news_items)
        if not targets:
            return (0, [])

        sem = asyncio.Semaphore(concurrency)
        success_count = 0
        errors: list[str] = []

        async def _analyze_one(n):
            nonlocal success_count
            async with sem:
                try:
                    await self.analyze_news_sentiment(n.id)
                    success_count += 1
                except Exception as exc:
                    logger.exception("Sentiment analysis failed for news %s", n.id)
                    errors.append(f"News {n.id}: {exc}")

        await asyncio.gather(*(_analyze_one(n) for n in targets))
        return (success_count, errors)
