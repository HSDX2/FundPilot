"""Scheduled AI analysis tasks — daily post-market analysis generation."""

import logging

from app.core.database import async_session_factory
from app.repositories.analysis_repo import AnalysisReportRepo, FundAdviceRepo
from app.repositories.fund_repo import FundEstimateRepo, FundNavRepo, FundRepo
from app.repositories.news_repo import NewsArticleRepo
from app.repositories.sector_repo import (
    SectorMoneyFlowRepo,
    SectorRepo,
    SectorSnapshotRepo,
)
from app.repositories.system_repo import AIProviderRepo
from app.services.analysis_service import AnalysisService

logger = logging.getLogger(__name__)


async def _create_analysis_service() -> AnalysisService | None:
    """Create an AnalysisService with real DB sessions."""
    try:
        session = async_session_factory()
        return AnalysisService(
            ai_provider_repo=AIProviderRepo(session),
            analysis_report_repo=AnalysisReportRepo(session),
            fund_advice_repo=FundAdviceRepo(session),
            sector_repo=SectorRepo(session),
            sector_snapshot_repo=SectorSnapshotRepo(session),
            sector_money_flow_repo=SectorMoneyFlowRepo(session),
            fund_repo=FundRepo(session),
            fund_nav_repo=FundNavRepo(session),
            fund_estimate_repo=FundEstimateRepo(session),
            news_repo=NewsArticleRepo(session),
        )
    except Exception as exc:
        logger.exception("Failed to create AnalysisService: %s", exc)
        return None


async def daily_sector_analysis_task() -> None:
    """Generate daily sector analysis reports for top sectors."""
    logger.info("Starting daily sector analysis task")
    svc = await _create_analysis_service()
    if svc is None:
        return

    try:
        reports = await svc.generate_all_sector_reports(
            report_type="daily", limit=10,
        )
        logger.info("Daily sector analysis done: %d reports generated", len(reports))
    except Exception:
        logger.exception("Daily sector analysis task failed")


async def daily_sentiment_analysis_task() -> None:
    """Run sentiment analysis on today's unanalyzed news."""
    logger.info("Starting daily sentiment analysis task")
    svc = await _create_analysis_service()
    if svc is None:
        return

    try:
        count = await svc.batch_analyze_sentiment(limit=50)
        logger.info("Daily sentiment analysis done: %d articles processed", count)
    except Exception:
        logger.exception("Daily sentiment analysis task failed")
