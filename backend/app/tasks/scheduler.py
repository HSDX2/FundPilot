"""APScheduler lifecycle management for the FastAPI app."""

import logging
from datetime import time as dt_time

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.core.constants import DEFAULT_COLLECTOR_INTERVALS, CollectorName
from app.core.database import async_session_factory
from app.repositories.system_repo import CollectorSettingRepo

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()

# Map collector names to task functions
from app.tasks.collect_tasks import (  # noqa: E402
    collect_estimate_task,
    collect_etf_list_task,
    collect_etf_task,
    collect_fund_list_task,
    collect_fund_nav_task,
    collect_market_sentiment_task,
    collect_news_task,
    collect_sector_daily_task,
    collect_sector_list_task,
    collect_sector_money_flow_task,
    collect_sector_realtime_task,
)

TASK_MAP = {
    CollectorName.FUND_LIST.value: collect_fund_list_task,
    CollectorName.ETF_LIST.value: collect_etf_list_task,
    CollectorName.ETF.value: collect_etf_task,
    CollectorName.SECTOR.value: collect_sector_realtime_task,
    CollectorName.SECTOR_LIST.value: collect_sector_list_task,
    CollectorName.SECTOR_DAILY.value: collect_sector_daily_task,
    CollectorName.SECTOR_MONEY_FLOW.value: collect_sector_money_flow_task,
    CollectorName.FUND_ESTIMATE.value: collect_estimate_task,
    CollectorName.FUND_NAV.value: collect_fund_nav_task,
    CollectorName.NEWS.value: collect_news_task,
    CollectorName.MARKET_SENTIMENT.value: collect_market_sentiment_task,
}


def _interval_to_cron(seconds: int) -> tuple[str, str, str, str, str]:
    """Convert seconds to a reasonable cron expression."""
    if seconds >= 86400:
        return ("7", "2", "*", "*", "*")
    if seconds >= 3600:
        return ("13", f"*/{max(1, seconds // 3600)}", "*", "*", "*")
    if seconds >= 60:
        return (f"*/{max(1, seconds // 60)}", "*", "*", "*", "*")
    return (f"*/{max(1, seconds)}", "*", "*", "*", "*")


def _schedule_config_to_cron(config: dict) -> tuple[str, str, str, str, str]:
    """Convert a schedule_config dict to a cron expression."""
    mode = config.get("mode", "interval")
    minute = "*"
    hour = "*"

    if mode == "specific_time":
        st = config.get("specific_time")
        if st:
            if isinstance(st, str):
                parts = st.split(":")
                hour = str(int(parts[0]))
                minute = str(int(parts[1])) if len(parts) > 1 else "0"
            elif isinstance(st, dt_time):
                hour = str(st.hour)
                minute = str(st.minute)

    if mode == "interval":
        interval_mins = config.get("interval_minutes")
        if interval_mins and interval_mins >= 1:
            if interval_mins >= 1440:
                minute, hour = "7", "2"
            elif interval_mins >= 60:
                hour = "13"
                minute = f"*/{max(1, interval_mins // 60)}"
            else:
                minute = f"*/{max(1, interval_mins)}"
                hour = "*"

    weekdays = config.get("weekdays")
    month_days = config.get("month_days")
    day_of_week = ",".join(str(d) for d in weekdays) if weekdays else "*"
    day = ",".join(str(d) for d in month_days) if month_days else "*"

    return (minute, hour, day, "*", day_of_week)


async def register_jobs() -> None:
    """Register all collection tasks as scheduled jobs, reading config from DB."""
    try:
        async with async_session_factory() as session:
            repo = CollectorSettingRepo(session)
            settings_list = await repo.list()
            settings_map = {s.collector_name: s for s in settings_list}
    except Exception:
        logger.warning("Cannot access DB, using default intervals")
        settings_map = {}

    for name, task_fn in TASK_MAP.items():
        setting = settings_map.get(name)
        if setting and setting.schedule_config:
            cron = _schedule_config_to_cron(setting.schedule_config)
        else:
            interval = (
                setting.interval_seconds
                if setting
                else DEFAULT_COLLECTOR_INTERVALS.get(CollectorName(name), 86400)
            )
            cron = _interval_to_cron(interval)

        scheduler.add_job(
            task_fn,
            trigger="cron",
            minute=cron[0],
            hour=cron[1],
            day=cron[2],
            month=cron[3],
            day_of_week=cron[4],
            id=f"collect_{name}",
            name=f"collect_{name}",
            replace_existing=True,
        )
        logger.info(
            "Registered job collect_%s: cron=%s",
            name, "/".join(cron),
        )


async def register_analysis_jobs() -> None:
    """Register AI analysis tasks (daily post-market)."""
    from app.tasks.analysis_tasks import (
        daily_sector_analysis_task,
        daily_sentiment_analysis_task,
    )

    # Sector analysis: 15:30 daily on weekdays
    scheduler.add_job(
        daily_sector_analysis_task,
        trigger="cron",
        minute="30",
        hour="15",
        day_of_week="1-5",
        id="analysis_sector_daily",
        name="analysis_sector_daily",
        replace_existing=True,
    )
    logger.info("Registered job analysis_sector_daily: 30/15/*/*/1-5")

    # Sentiment analysis: 16:00 daily on weekdays
    scheduler.add_job(
        daily_sentiment_analysis_task,
        trigger="cron",
        minute="0",
        hour="16",
        day_of_week="1-5",
        id="analysis_sentiment_daily",
        name="analysis_sentiment_daily",
        replace_existing=True,
    )
    logger.info("Registered job analysis_sentiment_daily: 0/16/*/*/1-5")


def init_scheduler(app) -> None:
    """Attach scheduler lifecycle to the FastAPI app."""

    @app.on_event("startup")
    async def start_scheduler():
        if not scheduler.running:
            await register_jobs()
            await register_analysis_jobs()
            scheduler.start()
            logger.info("APScheduler started with all jobs")

    @app.on_event("shutdown")
    async def stop_scheduler():
        if scheduler.running:
            scheduler.shutdown(wait=False)
            logger.info("APScheduler shut down")
