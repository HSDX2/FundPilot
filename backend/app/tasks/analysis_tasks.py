"""Scheduled AI analysis tasks — daily post-market analysis generation."""

import asyncio
import logging
from datetime import date

from app.core.database import async_session_factory
from app.core.task_lock import sentiment_lock
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
from app.services.analysis_service import AnalysisService

logger = logging.getLogger(__name__)


async def _create_analysis_service() -> AnalysisService | None:
    """Create an AnalysisService with real DB sessions."""
    try:
        session = async_session_factory()
        return AnalysisService(
            ai_provider_repo=AIProviderRepo(session),
            prompt_setting_repo=PromptSettingRepo(session),
            analysis_report_repo=AnalysisReportRepo(session),
            fund_advice_repo=FundAdviceRepo(session),
            sector_repo=SectorRepo(session),
            sector_snapshot_repo=SectorSnapshotRepo(session),
            sector_money_flow_repo=SectorMoneyFlowRepo(session),
            fund_repo=FundRepo(session),
            fund_nav_repo=FundNavRepo(session),
            fund_estimate_repo=FundEstimateRepo(session),
            news_repo=NewsArticleRepo(session),
            watchlist_repo=WatchedFundRepo(session),
        )
    except Exception as exc:
        logger.exception("Failed to create AnalysisService: %s", exc)
        return None


async def _close_service(svc: AnalysisService | None) -> None:
    """Close the session attached to an AnalysisService."""
    if svc is None:
        return
    try:
        session = svc._ai_provider_repo.session
        if session:
            await session.close()
    except Exception:
        logger.exception("Failed to close AnalysisService session")


async def run_news_sentiment_analysis_task(
    limit: int = 200,
    force: bool = False,
    start_date: date | None = None,
    end_date: date | None = None,
) -> int:
    """Run news sentiment analysis as a background task with lock protection."""
    svc = await _create_analysis_service()
    if svc is None:
        logger.error("Failed to create AnalysisService for sentiment task")
        return 0

    try:
        count, errors = await svc.batch_analyze_sentiment(
            limit=limit, force=force,
            start_date=start_date, end_date=end_date,
        )
        await svc._news_repo.session.commit()
        if errors:
            for err in errors[:5]:
                logger.error("Sentiment error: %s", err)
        logger.info("Sentiment analysis task done: %d/%d articles processed", count, limit)
        return count
    except Exception:
        await svc._news_repo.session.rollback()
        logger.exception("Sentiment analysis task failed")
        return 0
    finally:
        sentiment_lock.release()
        await _close_service(svc)


async def daily_sentiment_analysis_task() -> None:
    """Run sentiment analysis on today's unanalyzed news."""
    if not await sentiment_lock.try_acquire("news_sentiment_scheduled"):
        logger.info("Sentiment analysis already running, skipping scheduled run")
        return

    logger.info("Starting daily sentiment analysis task")
    await run_news_sentiment_analysis_task(limit=50)


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
    finally:
        await _close_service(svc)
