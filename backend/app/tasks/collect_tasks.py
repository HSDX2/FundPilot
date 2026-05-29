"""Scheduled data collection tasks.

All tasks check CollectorSetting before executing, and respect
trading session hours for market data tasks.
"""

import logging
from datetime import date, datetime, time

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
            FundNavRepo,
            FundRepo,
            FundEstimateRepo,
        )
        from app.repositories.news_repo import NewsArticleRepo, NewsSectorLinkRepo
        from app.repositories.sector_repo import (
            SectorMoneyFlowRepo,
            SectorRealtimeRepo,
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
            sector_realtime_repo=SectorRealtimeRepo(session),
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
    """ETF real-time spot collection (30s default).

    Reads start_date from CollectorSetting.schedule_config for backfill.
    None = today spot only.
    """
    if not is_trading_day() or not is_in_trading_session():
        return
    if not await _should_run("etf"):
        return

    logger.info("Running ETF collection task")
    svc = await _service_for("etf")
    if svc is None:
        return

    start_date = await _read_etf_start_date()
    try:
        result = await svc.collect_etf_spot(start_date=start_date)
        await _update_status("etf", "success")
        logger.info(
            "ETF collection done: ~%d updated",
            result.records_updated,
        )
    except Exception as exc:
        await _update_status("etf", "failed")
        logger.exception("ETF collection failed: %s", exc)
    finally:
        await svc.close()




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
    finally:
        await svc.close()


async def collect_fund_nav_history_task() -> None:
    """全量基金历史净值采集任务."""
    if not await _should_run("fund_nav_history"):
        return

    logger.info("Running fund NAV history collection task")
    svc = await _service_for("fund_nav_history")
    if svc is None:
        return

    try:
        start_date = None  # None = 回补全部历史数据
        new_only = False
        worker_count = 8
        config = await _read_other_config("fund_nav_history")
        if config is not None:
            raw = config.get("start_date")
            if raw is not None:
                if isinstance(raw, str):
                    start_date = date.fromisoformat(raw)
                elif isinstance(raw, date):
                    start_date = raw
            new_only = config.get("new_only", False)
            worker_count = config.get("worker_count", 8)

        result = await svc.collect_fund_nav_history(
            start_date=start_date, new_only=new_only,
            worker_count=worker_count,
        )
        await _update_status("fund_nav_history", "success")
        logger.info(
            "Fund NAV history done: +%d ~%d, errors=%d",
            result.records_added,
            result.records_updated,
            len(result.errors),
        )
    except Exception as exc:
        await _update_status("fund_nav_history", "failed")
        logger.exception("Fund NAV history collection failed: %s", exc)
    finally:
        await svc.close()


async def collect_fund_nav_daily_task() -> None:
    """每日基金净值增量采集任务（仅当天）。"""
    if not await _should_run("fund_nav_daily"):
        return

    logger.info("Running fund NAV daily collection task")
    svc = await _service_for("fund_nav_daily")
    if svc is None:
        return

    try:
        worker_count = 8
        config = await _read_other_config("fund_nav_daily")
        if config is not None:
            worker_count = config.get("worker_count", 8)

        result = await svc.collect_fund_nav_daily(worker_count=worker_count)
        await _update_status("fund_nav_daily", "success")
        logger.info(
            "Fund NAV daily done: +%d ~%d, errors=%d",
            result.records_added,
            result.records_updated,
            len(result.errors),
        )
    except Exception as exc:
        await _update_status("fund_nav_daily", "failed")
        logger.exception("Fund NAV daily collection failed: %s", exc)
    finally:
        await svc.close()


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
    finally:
        await svc.close()


async def collect_sector_batch_history_task() -> None:
    """全量板块历史数据采集任务（OHLC + 资金流向）。

    从 other_config 读取 start_date，留空 = 回补全部历史数据。
    """
    if not await _should_run("sector_batch_history"):
        return

    logger.info("Running sector batch history collection task")
    svc = await _service_for("sector_batch_history")
    if svc is None:
        return

    try:
        start_date = None  # None = 回补全部历史数据
        sector_new_only = False
        config = await _read_other_config("sector_batch_history")
        if config is not None:
            raw = config.get("start_date")
            if raw is not None:
                if isinstance(raw, str):
                    start_date = date.fromisoformat(raw)
                elif isinstance(raw, date):
                    start_date = raw
            sector_new_only = config.get("sector_new_only", False)

        result = await svc.collect_sectors_history(
            start_date=start_date, new_only=sector_new_only,
        )
        await _update_status("sector_batch_history", "success")
        logger.info(
            "Sector batch history done: +%d ~%d, errors=%d",
            result.records_added,
            result.records_updated,
            len(result.errors),
        )
    except Exception as exc:
        await _update_status("sector_batch_history", "failed")
        logger.exception("Sector batch history failed: %s", exc)
    finally:
        await svc.close()


async def collect_sector_batch_daily_task() -> None:
    """Batch daily incremental collection for all sectors (OHLC + money flow)."""
    if not await _should_run("sector_batch_daily"):
        return

    logger.info("Running sector batch daily collection task")
    svc = await _service_for("sector_batch_daily")
    if svc is None:
        return

    try:
        backfill_mf_detail = True
        config = await _read_other_config("sector_batch_daily")
        if config is not None:
            backfill_mf_detail = config.get("backfill_mf_detail", True)

        result = await svc.collect_sectors_daily(backfill_mf_detail=backfill_mf_detail)
        await _update_status("sector_batch_daily", "success")
        logger.info(
            "Sector batch daily done: +%d ~%d, errors=%d",
            result.records_added,
            result.records_updated,
            len(result.errors),
        )
    except Exception as exc:
        await _update_status("sector_batch_daily", "failed")
        logger.exception("Sector batch daily failed: %s", exc)
    finally:
        await svc.close()


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
    finally:
        await svc.close()


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
    finally:
        await svc.close()


async def _read_other_config(name: str) -> dict | None:
    """Read other_config from a collector's settings."""
    try:
        async with async_session_factory() as session:
            repo = CollectorSettingRepo(session)
            setting = await repo.get_by_name(name)
            if setting and setting.other_config:
                return dict(setting.other_config)
        return None
    except Exception:
        return None


async def _read_news_sources() -> list[str] | None:
    """Read news source config from the news collector's other_config."""
    config = await _read_other_config("news")
    if config is None:
        return None
    sources = config.get("sources")
    if sources and isinstance(sources, list):
        return [s for s in sources if isinstance(s, str)]
    return None


async def _read_etf_start_date() -> date | None:
    """Read start_date from the etf collector's other_config."""
    config = await _read_other_config("etf")
    if config is None:
        return None
    raw = config.get("start_date")
    if raw is None:
        return None
    if isinstance(raw, str):
        return date.fromisoformat(raw)
    if isinstance(raw, date):
        return raw
    return None


async def collect_fund_estimate_task() -> None:
    """基金实时估值采集任务（默认 5 分钟一次，交易时段执行）。"""
    if not is_trading_day() or not is_in_trading_session():
        return
    if not await _should_run("fund_estimate"):
        return

    logger.info("Running fund estimate collection task")
    svc = await _service_for("fund_estimate")
    if svc is None:
        return

    try:
        result = await svc.collect_fund_estimates()
        await _update_status("fund_estimate", "success")
        logger.info("Fund estimate done: ~%d updated", result.records_added + result.records_updated)
    except Exception as exc:
        await _update_status("fund_estimate", "failed")
        logger.exception("Fund estimate collection failed: %s", exc)
    finally:
        await svc.close()


async def collect_sector_realtime_task() -> None:
    """板块实时行情采集任务（默认 5 分钟一次，交易时段执行）。"""
    if not is_trading_day() or not is_in_trading_session():
        return
    if not await _should_run("sector_realtime"):
        return

    logger.info("Running sector realtime collection task")
    svc = await _service_for("sector_realtime")
    if svc is None:
        return

    try:
        result = await svc.collect_sectors_realtime()
        await _update_status("sector_realtime", "success")
        logger.info("Sector realtime done: ~%d sectors", result.records_added + result.records_updated)
    except Exception as exc:
        await _update_status("sector_realtime", "failed")
        logger.exception("Sector realtime collection failed: %s", exc)
    finally:
        await svc.close()


async def collect_news_sentiment_task() -> None:
    """新闻情绪分析采集任务（默认每小时一次）。"""
    if not await _should_run("news_sentiment"):
        return

    logger.info("Running news sentiment analysis task")
    svc = await _service_for("news_sentiment")
    if svc is None:
        return

    try:
        config = await _read_other_config("news_sentiment")
        sd = None
        ed = None
        cc = 3
        sl = 50
        if config is not None:
            raw = config.get("start_date")
            if raw is not None:
                sd = date.fromisoformat(raw) if isinstance(raw, str) else raw
            raw = config.get("end_date")
            if raw is not None:
                ed = date.fromisoformat(raw) if isinstance(raw, str) else raw
            cc = config.get("sentiment_concurrency", 3)
            sl = config.get("sentiment_limit", 50)

        result = await svc.collect_news_sentiment(
            limit=sl, start_date=sd, end_date=ed, concurrency=cc,
        )
        await _update_status("news_sentiment", "success")
        logger.info("News sentiment done: %d analyzed", result.records_added)
    except Exception as exc:
        await _update_status("news_sentiment", "failed")
        logger.exception("News sentiment analysis failed: %s", exc)
    finally:
        await svc.close()


async def collect_recommend_top_picks_task() -> None:
    """综合推荐定时采集任务（默认每4小时一次）。"""
    if not await _should_run("recommend_top_picks"):
        return

    logger.info("Running top picks recommendation task")
    svc = await _service_for("recommend_top_picks")
    if svc is None:
        return

    try:
        sl = 8
        config = await _read_other_config("recommend_top_picks")
        if config is not None:
            sl = config.get("recommend_limit", 8)

        result = await svc.collect_recommend_top_picks(limit=sl)
        await _update_status("recommend_top_picks", "success")
        logger.info("Top picks done: %d items", result.records_added)
    except Exception as exc:
        await _update_status("recommend_top_picks", "failed")
        logger.exception("Top picks recommendation failed: %s", exc)
    finally:
        await svc.close()


async def collect_recommend_dip_buy_task() -> None:
    """加仓推荐定时采集任务（默认每12小时一次）。"""
    if not await _should_run("recommend_dip_buy"):
        return

    logger.info("Running dip buy recommendation task")
    svc = await _service_for("recommend_dip_buy")
    if svc is None:
        return

    try:
        sl = 8
        md = 5.0
        mcd = 3
        config = await _read_other_config("recommend_dip_buy")
        if config is not None:
            sl = config.get("recommend_limit", 8)
            md = config.get("max_drawdown", 5.0)
            mcd = config.get("min_consecutive_days", 3)

        result = await svc.collect_recommend_dip_buy(
            limit=sl, max_drawdown=md, min_consecutive_days=mcd,
        )
        await _update_status("recommend_dip_buy", "success")
        logger.info("Dip buy done: %d items", result.records_added)
    except Exception as exc:
        await _update_status("recommend_dip_buy", "failed")
        logger.exception("Dip buy recommendation failed: %s", exc)
    finally:
        await svc.close()
