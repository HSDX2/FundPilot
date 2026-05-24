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
from app.models.analysis import AnalysisReport, FundAdvice
from app.repositories.analysis_repo import AnalysisReportRepo, FundAdviceRepo
from app.repositories.fund_repo import FundEstimateRepo, FundNavRepo, FundRepo
from app.repositories.news_repo import NewsArticleRepo
from app.repositories.sector_repo import (
    SectorMoneyFlowRepo,
    SectorRepo,
    SectorSnapshotRepo,
)
from app.repositories.system_repo import AIProviderRepo

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
        analysis_report_repo: AnalysisReportRepo,
        fund_advice_repo: FundAdviceRepo,
        sector_repo: SectorRepo,
        sector_snapshot_repo: SectorSnapshotRepo,
        sector_money_flow_repo: SectorMoneyFlowRepo,
        fund_repo: FundRepo,
        fund_nav_repo: FundNavRepo,
        fund_estimate_repo: FundEstimateRepo,
        news_repo: NewsArticleRepo,
    ) -> None:
        self._ai_provider_repo = ai_provider_repo
        self._report_repo = analysis_report_repo
        self._advice_repo = fund_advice_repo
        self._sector_repo = sector_repo
        self._snapshot_repo = sector_snapshot_repo
        self._money_flow_repo = sector_money_flow_repo
        self._fund_repo = fund_repo
        self._nav_repo = fund_nav_repo
        self._est_repo = fund_estimate_repo
        self._news_repo = news_repo

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
            f"- {s.timestamp.strftime('%m-%d')}: {s.change_pct:+.2f}%"
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

        prompt_template = _SECTOR_PROMPT_MAP.get(
            report_type, SECTOR_ANALYSIS_USER_DAILY
        )
        user_prompt = prompt_template.format(
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
            system_prompt=SECTOR_ANALYSIS_SYSTEM,
            user_prompt=user_prompt,
        )

        report = AnalysisReport(
            date=today,
            report_type=report_type,
            content=result,
            ai_model=ai.model,
        )
        self._report_repo.session.add(report)
        await self._report_repo.session.flush()
        return report

    async def generate_all_sector_reports(
        self, report_type: str = "daily", limit: int = 10,
    ) -> list[AnalysisReport]:
        """Generate reports for top sectors by latest snapshot."""
        from sqlalchemy import func, select

        from app.models.sector import SectorSnapshot

        ts_stmt = select(func.max(SectorSnapshot.timestamp))
        ts_result = await self._sector_repo.session.execute(ts_stmt)
        latest_ts = ts_result.scalar()
        if latest_ts is None:
            sectors = list(await self._sector_repo.get_all_active())
            latest_snapshots = [(None, s) for s in sectors[:limit]]
        else:
            latest_snapshots = await self._snapshot_repo.get_rank_by_timestamp(
                timestamp=latest_ts, limit=limit,
            )

        reports = []
        for snap, sector in latest_snapshots:
            try:
                report = await self.generate_sector_report(
                    sector.id, report_type,
                )
                reports.append(report)
            except Exception:
                logger.exception(
                    "Failed to generate report for sector %s", sector.id,
                )
        return reports

    # ── Fund Advice ───────────────────────────────────────────────────

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

        # Load latest estimate
        estimate = await self._est_repo.get_latest_by_fund(fund_id)
        estimate_str = "暂无实时估值"
        if estimate:
            estimate_str = (
                f"估值: {estimate.estimate_nav:.4f}, "
                f"涨跌: {estimate.estimate_change_pct:+.2f}%"
                if estimate.estimate_change_pct is not None
                else f"估值: {estimate.estimate_nav:.4f}"
            )

        # News
        news_titles = "暂无"
        news_items, _ = await self._news_repo.search(
            keyword=fund.name, page=1, page_size=3,
        )
        if news_items:
            news_titles = "\n".join(f"- {n.title}" for n in news_items)

        user_prompt = FUND_ADVICE_USER.format(
            fund_name=fund.name,
            fund_code=fund.code,
            fund_type=fund.type or "未知",
            latest_nav=navs[0].nav if navs else "N/A",
            accumulated_nav=navs[0].accumulated_nav if navs else "N/A",
            nav_history=nav_history,
            estimate=estimate_str,
            sector_performance="暂无关联板块数据",
            news_titles=news_titles,
        )

        result = await ai.analyze(
            system_prompt=FUND_ADVICE_SYSTEM,
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
        user_prompt = NEWS_SENTIMENT_USER.format(
            title=news.title or "",
            source=news.source or "未知",
            published_at=news.published_at.isoformat() if news.published_at else "未知",
            content=content[:2000],
        )

        result = await ai.analyze(
            system_prompt=NEWS_SENTIMENT_SYSTEM,
            user_prompt=user_prompt,
        )

        score_val = result.get("score")
        try:
            news.sentiment_score = float(score_val) if score_val is not None else None
        except (TypeError, ValueError):
            news.sentiment_score = None

        await self._news_repo.session.flush()

    async def batch_analyze_sentiment(
        self, limit: int = 20, concurrency: int = 3,
    ) -> int:
        """Analyze sentiment for news without scores. Returns count processed."""
        today = date.today()
        news_items, _ = await self._news_repo.search(
            start=datetime.combine(today - timedelta(days=3), datetime.min.time()),
            end=datetime.combine(today, datetime.max.time()),
            page=1,
            page_size=limit,
        )

        unanalyzed = [n for n in news_items if n.sentiment_score is None]
        if not unanalyzed:
            return 0

        sem = asyncio.Semaphore(concurrency)

        async def _analyze_one(n):
            async with sem:
                try:
                    await self.analyze_news_sentiment(n.id)
                except Exception:
                    logger.exception("Sentiment analysis failed for news %s", n.id)

        await asyncio.gather(*(_analyze_one(n) for n in unanalyzed))
        return len(unanalyzed)
