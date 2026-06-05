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
    collect_etf_task,
    collect_fund_estimate_task,
    collect_fund_list_task,
    collect_fund_nav_daily_task,
    collect_fund_nav_history_task,
    collect_market_sentiment_task,
    collect_news_task,
    collect_sector_batch_daily_task,
    collect_sector_batch_history_task,
    collect_sector_list_task,
    collect_sector_realtime_task,
    collect_news_sentiment_task,
    collect_recommend_top_picks_task,
    collect_recommend_dip_buy_task,
)

TASK_MAP = {
    CollectorName.FUND_LIST.value: collect_fund_list_task,
    CollectorName.ETF.value: collect_etf_task,
    CollectorName.SECTOR_LIST.value: collect_sector_list_task,
    CollectorName.FUND_NAV_HISTORY.value: collect_fund_nav_history_task,
    CollectorName.FUND_NAV_DAILY.value: collect_fund_nav_daily_task,
    CollectorName.NEWS.value: collect_news_task,
    CollectorName.MARKET_SENTIMENT.value: collect_market_sentiment_task,
    CollectorName.SECTOR_BATCH_HISTORY.value: collect_sector_batch_history_task,
    CollectorName.SECTOR_BATCH_DAILY.value: collect_sector_batch_daily_task,
    CollectorName.FUND_ESTIMATE.value: collect_fund_estimate_task,
    CollectorName.SECTOR_REALTIME.value: collect_sector_realtime_task,
    CollectorName.NEWS_SENTIMENT.value: collect_news_sentiment_task,
    CollectorName.RECOMMEND_TOP_PICKS.value: collect_recommend_top_picks_task,
    CollectorName.RECOMMEND_DIP_BUY.value: collect_recommend_dip_buy_task,
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
            # 从激活时间窗口取起始分钟作为 cron 基准分钟
            base_minute = 0
            active_start = config.get("active_start_time")
            if active_start and isinstance(active_start, str) and ":" in active_start:
                base_minute = int(active_start.split(":")[1])
            if interval_mins >= 1440:
                minute, hour = "7", "2"
            elif interval_mins >= 60:
                minute = str(base_minute)
                hour = f"*/{max(1, interval_mins // 60)}"
            else:
                minute = f"*/{max(1, interval_mins)}"
                hour = "*"

    weekdays = config.get("weekdays")
    month_days = config.get("month_days")
    # APScheduler 的 day_of_week: 0=周一, 1=周二 ... 6=周日
    # 前端存储的是 isoweekday: 1=周一 ... 7=周日
    if weekdays:
        day_of_week = ",".join(str(d - 1) for d in weekdays if 1 <= d <= 7)
    else:
        day_of_week = "*"
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
            config = dict(setting.schedule_config)
            # If interval mode has no interval_minutes, derive from interval_seconds
            if config.get("mode", "interval") == "interval" and not config.get("interval_minutes"):
                default_secs = (
                    setting.interval_seconds
                    or DEFAULT_COLLECTOR_INTERVALS.get(CollectorName(name), 86400)
                )
                config["interval_minutes"] = max(1, default_secs // 60)
            cron = _schedule_config_to_cron(config)
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


async def reschedule_job(
    collector_name: str,
    *,
    is_active: bool | None = None,
    schedule_config: dict | None = None,
    interval_seconds: int | None = None,
) -> None:
    """根据参数实时重新调度单个采集任务，无需重启后端。

    调用方传入最新值（而非本函数重新读库），避免事务提交时序问题。
    """
    task_fn = TASK_MAP.get(collector_name)
    if task_fn is None:
        logger.warning("reschedule_job: unknown collector %s", collector_name)
        return

    job_id = f"collect_{collector_name}"

    # 未激活或无定时策略 → 移除 job
    if is_active is False or not schedule_config:
        try:
            scheduler.remove_job(job_id)
            logger.info("Removed job %s (inactive)", job_id)
        except Exception:
            pass  # job 可能不存在
        return

    config = dict(schedule_config)
    if config.get("mode", "interval") == "interval" and not config.get("interval_minutes"):
        default_secs = interval_seconds or DEFAULT_COLLECTOR_INTERVALS.get(
            CollectorName(collector_name), 86400,
        )
        config["interval_minutes"] = max(1, default_secs // 60)

    cron = _schedule_config_to_cron(config)

    scheduler.add_job(
        task_fn,
        trigger="cron",
        minute=cron[0], hour=cron[1], day=cron[2], month=cron[3], day_of_week=cron[4],
        id=job_id,
        name=job_id,
        replace_existing=True,
    )
    logger.info("Rescheduled job %s: cron=%s", job_id, "/".join(cron))


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
