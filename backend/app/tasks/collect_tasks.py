"""Scheduled data collection tasks.

All tasks check CollectorSetting before executing, and respect
trading session hours for market data tasks.
"""

import logging
from datetime import datetime, time

from app.core.database import async_session_factory
from app.repositories.system_repo import CollectorSettingRepo
from app.services.collector_service import CollectorService

logger = logging.getLogger(__name__)

# A-share trading session times
MORNING_START = time(9, 30)
MORNING_END = time(11, 30)
AFTERNOON_START = time(13, 0)
AFTERNOON_END = time(15, 0)


def is_in_trading_session() -> bool:
    """Check if current time is within A-share trading hours."""
    now = datetime.now().time()
    if MORNING_START <= now <= MORNING_END:
        return True
    if AFTERNOON_START <= now <= AFTERNOON_END:
        return True
    return False


def is_trading_day() -> bool:
    """Simple check: weekdays only. Phase 2 can add holiday awareness."""
    return datetime.now().weekday() < 5


async def _should_run(name: str) -> bool:
    """Check if a collector should run based on settings and schedule config."""
    async with async_session_factory() as session:
        repo = CollectorSettingRepo(session)
        setting = await repo.get_by_name(name)
        if setting is None:
            return False
        if not setting.is_active:
            return False
        if setting.schedule_config:
            return _evaluate_schedule(setting.schedule_config)
        return True


def _evaluate_schedule(config: dict) -> bool:
    """Check if current time matches the schedule config.

    Returns True if all configured conditions are met:
    - Current time is within active_start_time / active_end_time window
    - Current day matches weekdays / month_days dimension
    """
    now = datetime.now()
    now_time = now.time()

    # Check active time window
    active_start = config.get("active_start_time")
    active_end = config.get("active_end_time")
    if active_start and active_end:
        start = _parse_time(active_start)
        end = _parse_time(active_end)
        if start and end and not (start <= now_time <= end):
            return False

    # Check weekday dimension
    weekdays = config.get("weekdays")
    if weekdays:
        iso_weekday = now.isoweekday()
        if iso_weekday not in weekdays:
            return False

    # Check month day dimension
    month_days = config.get("month_days")
    if month_days:
        if now.day not in month_days:
            return False

    return True


def _parse_time(value: str | time) -> time | None:
    """Parse a time value from config (string or time object)."""
    if isinstance(value, time):
        return value
    if isinstance(value, str):
        parts = value.split(":")
        try:
            sec = int(parts[2]) if len(parts) > 2 else 0
            return time(int(parts[0]), int(parts[1]), sec)
        except (ValueError, IndexError):
            return None
    return None


async def _service_for(name: str) -> CollectorService | None:
    """Create a CollectorService with DB repos attached."""
    try:
        session = async_session_factory()
        from app.repositories.fund_repo import (
            FundEstimateRepo,
            FundNavRepo,
            FundRepo,
        )
        from app.repositories.news_repo import NewsArticleRepo, NewsSectorLinkRepo
        from app.repositories.sector_repo import (
            SectorMoneyFlowRepo,
            SectorRepo,
            SectorSnapshotRepo,
        )
        from app.repositories.sentiment_repo import MarketSentimentRepo
        from app.repositories.system_repo import CollectLogRepo

        svc = CollectorService(
            fund_repo=FundRepo(session),
            fund_nav_repo=FundNavRepo(session),
            fund_estimate_repo=FundEstimateRepo(session),
            sector_repo=SectorRepo(session),
            sector_snapshot_repo=SectorSnapshotRepo(session),
            sector_money_flow_repo=SectorMoneyFlowRepo(session),
            news_repo=NewsArticleRepo(session),
            news_sector_link_repo=NewsSectorLinkRepo(session),
            sentiment_repo=MarketSentimentRepo(session),
            collect_log_repo=CollectLogRepo(session),
        )
        return svc
    except Exception as exc:
        logger.exception("Failed to create CollectorService: %s", exc)
        return None


async def _update_status(name: str, status: str) -> None:
    """Update a collector's last_run_at and last_status."""
    try:
        async with async_session_factory() as session:
            repo = CollectorSettingRepo(session)
            await repo.update_last_run(name, status)
            await session.commit()
    except Exception as exc:
        logger.error("Failed to update status for %s: %s", name, exc)


async def collect_etf_task() -> None:
    """ETF real-time spot collection (30s default)."""
    if not is_trading_day() or not is_in_trading_session():
        return
    if not await _should_run("etf"):
        return

    logger.info("Running ETF collection task")
    svc = await _service_for("etf")
    if svc is None:
        return

    try:
        result = await svc.collect_etf_spot()
        await _update_status("etf", "success")
        logger.info(
            "ETF collection done: +%d records",
            result.records_added,
        )
    except Exception as exc:
        await _update_status("etf", "failed")
        logger.exception("ETF collection failed: %s", exc)


async def collect_sector_realtime_task() -> None:
    """Sector real-time snapshot collection (1min default)."""
    if not is_trading_day() or not is_in_trading_session():
        return
    if not await _should_run("sector"):
        return

    logger.info("Running sector realtime collection task")
    svc = await _service_for("sector")
    if svc is None:
        return

    try:
        result = await svc.collect_sector_realtime()
        await _update_status("sector", "success")
        logger.info(
            "Sector realtime done: +%d records",
            result.records_added,
        )
    except Exception as exc:
        await _update_status("sector", "failed")
        logger.exception("Sector realtime failed: %s", exc)


async def collect_estimate_task() -> None:
    """Fund NAV estimate collection (5min default)."""
    if not is_trading_day() or not is_in_trading_session():
        return
    if not await _should_run("fund_estimate"):
        return

    logger.info("Running fund estimate collection task")
    svc = await _service_for("fund_estimate")
    if svc is None:
        return

    try:
        result = await svc.collect_estimates()
        await _update_status("fund_estimate", "success")
        logger.info(
            "Estimate collection done: +%d records",
            result.records_added,
        )
    except Exception as exc:
        await _update_status("fund_estimate", "failed")
        logger.exception("Estimate collection failed: %s", exc)


async def collect_fund_list_task() -> None:
    """Daily fund list collection task."""
    if not await _should_run("fund_list"):
        return

    logger.info("Running fund list collection task")
    svc = await _service_for("fund_list")
    if svc is None:
        return

    try:
        result = await svc.collect_fund_list()
        await _update_status("fund_list", "success")
        logger.info(
            "Fund list collection done: +%d ~%d",
            result.records_added,
            result.records_updated,
        )
    except Exception as exc:
        await _update_status("fund_list", "failed")
        logger.exception("Fund list collection failed: %s", exc)


async def collect_etf_list_task() -> None:
    """Daily ETF list collection task."""
    if not await _should_run("etf_list"):
        return

    logger.info("Running ETF list collection task")
    svc = await _service_for("etf_list")
    if svc is None:
        return

    try:
        result = await svc.collect_etf_list()
        await _update_status("etf_list", "success")
        logger.info(
            "ETF list collection done: +%d ~%d",
            result.records_added,
            result.records_updated,
        )
    except Exception as exc:
        await _update_status("etf_list", "failed")
        logger.exception("ETF list collection failed: %s", exc)


async def collect_fund_nav_task() -> None:
    """Daily fund NAV collection task."""
    if not await _should_run("fund_nav"):
        return

    logger.info("Running fund NAV collection task")
    svc = await _service_for("fund_nav")
    if svc is None:
        return

    try:
        result = await svc.collect_fund_nav_all()
        await _update_status("fund_nav", "success")
        logger.info(
            "Fund NAV collection done: +%d ~%d, errors=%d",
            result.records_added,
            result.records_updated,
            len(result.errors),
        )
    except Exception as exc:
        await _update_status("fund_nav", "failed")
        logger.exception("Fund NAV collection failed: %s", exc)


async def collect_sector_list_task() -> None:
    """Daily sector list collection task."""
    if not await _should_run("sector_list"):
        return

    logger.info("Running sector list collection task")
    svc = await _service_for("sector_list")
    if svc is None:
        return

    try:
        result = await svc.collect_sector_list()
        await _update_status("sector_list", "success")
        logger.info(
            "Sector list collection done: +%d ~%d",
            result.records_added,
            result.records_updated,
        )
    except Exception as exc:
        await _update_status("sector_list", "failed")
        logger.exception("Sector list collection failed: %s", exc)


async def collect_sector_daily_task() -> None:
    """Daily sector historical data collection task."""
    if not await _should_run("sector_daily"):
        return

    logger.info("Running sector daily collection task")
    svc = await _service_for("sector_daily")
    if svc is None:
        return

    try:
        result = await svc.collect_sector_daily_all()
        await _update_status("sector_daily", "success")
        logger.info(
            "Sector daily collection done: +%d ~%d, errors=%d",
            result.records_added,
            result.records_updated,
            len(result.errors),
        )
    except Exception as exc:
        await _update_status("sector_daily", "failed")
        logger.exception("Sector daily collection failed: %s", exc)


async def collect_sector_money_flow_task() -> None:
    """Daily sector money flow collection task."""
    if not await _should_run("sector_money_flow"):
        return

    logger.info("Running sector money flow collection task")
    svc = await _service_for("sector_money_flow")
    if svc is None:
        return

    try:
        result = await svc.collect_sector_money_flow()
        await _update_status("sector_money_flow", "success")
        logger.info(
            "Sector money flow collection done: +%d ~%d",
            result.records_added,
            result.records_updated,
        )
    except Exception as exc:
        await _update_status("sector_money_flow", "failed")
        logger.exception("Sector money flow collection failed: %s", exc)


async def collect_news_task() -> None:
    """News collection task (10min default).

    Reads source configuration from CollectorSetting.schedule_config.sources.
    Empty or missing = collect all sources.
    """
    if not await _should_run("news"):
        return

    svc = await _service_for("news")
    if svc is None:
        return

    sources = await _read_news_sources()
    try:
        result = await svc.collect_news(sources=sources)
        await _update_status("news", "success")
        logger.info(
            "News collection done [%s]: +%d records",
            ",".join(sources) if sources else "all",
            result.records_added,
        )
    except Exception as exc:
        await _update_status("news", "failed")
        logger.exception("News collection failed: %s", exc)


async def collect_market_sentiment_task() -> None:
    """Daily market sentiment collection task."""
    if not await _should_run("market_sentiment"):
        return

    logger.info("Running market sentiment collection task")
    svc = await _service_for("market_sentiment")
    if svc is None:
        return

    try:
        result = await svc.collect_market_sentiment()
        await _update_status("market_sentiment", "success")
        logger.info(
            "Market sentiment collection done: +%d records",
            result.records_added,
        )
    except Exception as exc:
        await _update_status("market_sentiment", "failed")
        logger.exception("Market sentiment collection failed: %s", exc)


async def _read_news_sources() -> list[str] | None:
    """Read news source config from the news collector setting."""
    try:
        async with async_session_factory() as session:
            repo = CollectorSettingRepo(session)
            setting = await repo.get_by_name("news")
            if setting and setting.schedule_config:
                sources = setting.schedule_config.get("sources")
                if sources and isinstance(sources, list):
                    return [s for s in sources if isinstance(s, str)]
        return None
    except Exception:
        return None
