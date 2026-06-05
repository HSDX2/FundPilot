"""采集控制 API 路由."""

import asyncio
import logging
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_collector_service,
    get_collector_setting_repo,
)
from app.core.database import async_session_factory, get_db
from app.core.errors import CollectorBusyError, CollectorNotFoundError, InvalidArgumentError
from app.core.response import ApiResponse
from app.repositories.fund_repo import (
    FundEstimateRepo,
    FundNavRepo,
    FundRepo,
)
from app.repositories.news_repo import NewsArticleRepo, NewsSectorLinkRepo
from app.repositories.sector_repo import (
    SectorMoneyFlowRepo,
    SectorRealtimeRepo,
    SectorRepo,
    SectorSnapshotRepo,
)
from app.repositories.sentiment_repo import MarketSentimentRepo
from app.repositories.system_repo import (
    CollectLogRepo,
    CollectLogRepo as BgCollectLogRepo,
    CollectorSettingRepo,
)
from app.core.constants import COLLECTOR_META
from app.schemas.system import (
    CollectLogListData,
    CollectLogResponse,
    CollectorSettingResponse,
    CollectorSettingUpdate,
    CollectorTriggerRequest,
    CollectResultResponse,
    OtherConfigUpdate,
    ScheduleConfigUpdate,
    TaskStatusResponse,
)
from app.services.collector_service import (
    ALL_COLLECTORS,
    CollectorService,
    TaskAlreadyRunningError,
)

logger = logging.getLogger(__name__)

# Keep references to background tasks to prevent GC
_bg_tasks: set[asyncio.Task] = set()

router = APIRouter(prefix="/collect", tags=["数据采集"])


async def _read_other_config(name: str) -> dict | None:
    """Read other_config from the collector's settings."""
    try:
        async with async_session_factory() as session:
            repo = CollectorSettingRepo(session)
            setting = await repo.get_by_name(name)
            if setting and setting.other_config:
                return dict(setting.other_config)
        return None
    except Exception:
        return None


async def _read_config_start_date(name: str) -> date | None:
    """Read start_date from the collector's other_config as a fallback."""
    config = await _read_other_config(name)
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


async def _run_collector_background(
    body: CollectorTriggerRequest,
) -> None:
    """Execute a collector in the background using the main event loop."""
    session = async_session_factory()
    try:
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
            collect_log_repo=BgCollectLogRepo(session),
        )

        if body.collector == "news":
            await svc.collect_news(sources=body.sources)
        elif body.collector == "sector_batch_history":
            start_date = body.start_date or await _read_config_start_date(
                "sector_batch_history",
            )
            sector_new_only = False
            if body.sector_new_only is not None:
                sector_new_only = body.sector_new_only
            else:
                config = await _read_other_config("sector_batch_history")
                if config is not None and "sector_new_only" in config:
                    sector_new_only = config["sector_new_only"]
            await svc.collect_sectors_history(
                start_date=start_date, new_only=sector_new_only,
            )
        elif body.collector == "sector_batch_daily":
            backfill_mf_detail = True
            if body.backfill_mf_detail is not None:
                backfill_mf_detail = body.backfill_mf_detail
            else:
                config = await _read_other_config("sector_batch_daily")
                if config is not None and "backfill_mf_detail" in config:
                    backfill_mf_detail = config["backfill_mf_detail"]
            await svc.collect_sectors_daily(backfill_mf_detail=backfill_mf_detail)
        elif body.collector == "fund_nav_history":
            start_date = body.start_date or await _read_config_start_date(
                "fund_nav_history",
            )
            new_only = False
            worker_count = 8
            if body.new_only is not None:
                new_only = body.new_only
            if body.worker_count is not None:
                worker_count = body.worker_count
            config = await _read_other_config("fund_nav_history")
            if config is not None:
                if new_only is False and "new_only" in config:
                    new_only = config["new_only"]
                if "worker_count" in config:
                    worker_count = config["worker_count"]
            await svc.collect_fund_nav_history(
                start_date=start_date, new_only=new_only,
                worker_count=worker_count,
            )
        elif body.collector == "fund_nav_daily":
            wc = body.worker_count or 8
            if body.worker_count is None:
                config = await _read_other_config("fund_nav_daily")
                if config is not None and "worker_count" in config:
                    wc = config["worker_count"]
            await svc.collect_fund_nav_daily(worker_count=wc)
        elif body.collector == "fund_list":
            await svc.collect_fund_list(fund_type=body.fund_type)
        elif body.collector == "etf":
            start_date = body.start_date or await _read_config_start_date("etf")
            await svc.collect_etf_spot(start_date=start_date)
        elif body.collector == "sector_list":
            await svc.collect_sector_list()
        elif body.collector == "market_sentiment":
            await svc.collect_market_sentiment()
        elif body.collector == "fund_estimate":
            await svc.collect_fund_estimates()
        elif body.collector == "sector_realtime":
            await svc.collect_sectors_realtime()
        elif body.collector == "news_sentiment":
            sd = body.start_date
            ed = body.end_date
            cc = body.sentiment_concurrency
            sl = body.sentiment_limit
            if sd is None or ed is None or cc is None or sl is None:
                config = await _read_other_config("news_sentiment")
                if config is not None:
                    if sd is None and "start_date" in config:
                        raw = config["start_date"]
                        sd = date.fromisoformat(raw) if isinstance(raw, str) else raw
                    if ed is None and "end_date" in config:
                        raw = config["end_date"]
                        ed = date.fromisoformat(raw) if isinstance(raw, str) else raw
                    if cc is None and "sentiment_concurrency" in config:
                        cc = config["sentiment_concurrency"]
                    if sl is None and "sentiment_limit" in config:
                        sl = config["sentiment_limit"]
            await svc.collect_news_sentiment(
                limit=sl or 50, start_date=sd, end_date=ed, concurrency=cc or 3,
            )
        elif body.collector == "recommend_top_picks":
            rl = body.recommend_limit or 8
            if body.recommend_limit is None:
                config = await _read_other_config("recommend_top_picks")
                if config is not None:
                    rl = config.get("recommend_limit", 8)
            await svc.collect_recommend_top_picks(limit=rl)
        elif body.collector == "recommend_dip_buy":
            rl = body.recommend_limit or 8
            md = body.max_drawdown or 5.0
            mcd = body.min_consecutive_days or 3
            if body.recommend_limit is None:
                config = await _read_other_config("recommend_dip_buy")
                if config is not None:
                    rl = config.get("recommend_limit", 8)
                    md = config.get("max_drawdown", 5.0)
                    mcd = config.get("min_consecutive_days", 3)
            await svc.collect_recommend_dip_buy(
                limit=rl, max_drawdown=md or 5.0,
                min_consecutive_days=mcd or 3,
            )
    except Exception:
        logger.exception("Background collector %s failed", body.collector)
        CollectorService._finish_task(body.collector, "Background task crashed", errors=True)
    finally:
        await session.close()


@router.post(
    "/trigger",
    summary="手动触发数据采集",
    description=(
        "手动触发指定的数据采集任务。任务在后台异步执行，"
        "通过 GET /collect/status 查询进度。"
    ),
)
async def trigger_collect(
    body: CollectorTriggerRequest,
    service: CollectorService = Depends(get_collector_service),
):
    """手动触发指定采集器执行一次数据采集."""
    if body.collector not in ALL_COLLECTORS:
        raise CollectorNotFoundError(body.collector)

    try:
        CollectorService._check_not_running(body.collector)
    except TaskAlreadyRunningError:
        raise CollectorBusyError(body.collector) from None

    # Mark as running immediately so status polling picks it up
    CollectorService._start_task(body.collector, 0, "Starting...")

    task = asyncio.create_task(_run_collector_background(body))
    _bg_tasks.add(task)
    task.add_done_callback(_bg_tasks.discard)

    return ApiResponse.success(
        CollectResultResponse(
            collector_name=body.collector,
            records_added=0,
            records_updated=0,
            errors=[],
        ).model_dump()
    )


@router.get(
    "/settings",
    summary="查询采集器配置",
    description="获取所有数据采集器的配置信息，包括采集间隔和启用状态",
)
async def list_collector_settings(
    repo: CollectorSettingRepo = Depends(get_collector_setting_repo),
):
    settings = await repo.list()
    # Only return collectors that have active task implementations
    from app.tasks.scheduler import TASK_MAP
    valid_names = set(TASK_MAP.keys())
    items = [
        CollectorSettingResponse.model_validate(s).model_dump()
        for s in settings
        if s.collector_name in valid_names
    ]
    return ApiResponse.success({"items": items})


@router.put(
    "/settings/{collector_name}",
    summary="更新采集器配置",
    description="修改指定采集器的采集间隔或启用/禁用状态",
)
async def update_collector_setting(
    collector_name: Annotated[
        str,
        Path(
            description=(
                "采集器名称：fund_list / etf / sector_list / "
                "fund_nav_history / fund_nav_daily / news / "
                "market_sentiment / sector_batch_history / "
                "sector_batch_daily / fund_estimate / sector_realtime"
            ),
        ),
    ],
    body: CollectorSettingUpdate,
    repo: CollectorSettingRepo = Depends(get_collector_setting_repo),
):
    setting = await repo.get_by_name(collector_name)
    if setting is None:
        raise CollectorNotFoundError(collector_name)

    # 启用时必须已有定时策略
    if body.is_active is True and not setting.schedule_config:
        raise InvalidArgumentError(
            "启用采集器前请先配置定时策略"
        )

    update_data = {}
    if body.display_name is not None:
        update_data["display_name"] = body.display_name
    if body.description is not None:
        update_data["description"] = body.description
    if body.interval_seconds is not None:
        update_data["interval_seconds"] = body.interval_seconds
    if body.is_active is not None:
        update_data["is_active"] = body.is_active
    if body.sort_order is not None:
        update_data["sort_order"] = body.sort_order

    if update_data:
        await repo.update(setting.id, update_data)

    # 实时同步 APScheduler：is_active / interval_seconds 变更影响定时调度
    if "is_active" in update_data or "interval_seconds" in update_data:
        from app.tasks.scheduler import reschedule_job
        await reschedule_job(
            collector_name,
            is_active=update_data.get("is_active", setting.is_active),
            schedule_config=dict(setting.schedule_config) if setting.schedule_config else None,
            interval_seconds=update_data.get("interval_seconds", setting.interval_seconds),
        )

    updated = await repo.get_by_name(collector_name)
    return ApiResponse.success(
        CollectorSettingResponse.model_validate(updated).model_dump()
    )


@router.put(
    "/settings/{collector_name}/schedule",
    summary="更新采集器定时配置",
    description=(
        "配置采集器的灵活定时策略。支持两种模式："
        "interval（间隔执行，如每60分钟）和 "
        "specific_time（指定时刻，如每日12:00）。"
        "可设置激活时间窗口和日期维度（星期/月日）。"
    ),
)
async def update_collector_schedule(
    collector_name: Annotated[
        str,
        Path(description="采集器名称"),
    ],
    body: ScheduleConfigUpdate,
    repo: CollectorSettingRepo = Depends(get_collector_setting_repo),
):
    setting = await repo.get_by_name(collector_name)
    if setting is None:
        raise CollectorNotFoundError(collector_name)

    # 用 dict() 拷贝避免 SQLAlchemy JSONB 就地变更丢失
    current = dict(setting.schedule_config) if setting.schedule_config else {}
    body_dict = body.model_dump(mode="json")
    for key, value in body_dict.items():
        if value is None:
            current.pop(key, None)  # null 表示清空该字段
        else:
            current[key] = value
    if not current and setting.is_active:
        raise InvalidArgumentError(
            "定时策略已清空，请先禁用采集器或配置新的定时策略"
        )
    await repo.update(setting.id, {"schedule_config": current})

    # 实时同步 APScheduler：定时策略变更始终需要重调度
    from app.tasks.scheduler import reschedule_job
    await reschedule_job(
        collector_name,
        is_active=setting.is_active,
        schedule_config=current,
        interval_seconds=setting.interval_seconds,
    )

    updated = await repo.get_by_name(collector_name)
    return ApiResponse.success(
        CollectorSettingResponse.model_validate(updated).model_dump()
    )


@router.put(
    "/settings/{collector_name}/other-config",
    summary="更新采集器额外参数配置",
    description="配置采集器的额外参数（基金类型、新闻源、数据起始日期等）。",
)
async def update_collector_other_config(
    collector_name: Annotated[
        str,
        Path(description="采集器名称"),
    ],
    body: OtherConfigUpdate,
    repo: CollectorSettingRepo = Depends(get_collector_setting_repo),
):
    setting = await repo.get_by_name(collector_name)
    if setting is None:
        raise CollectorNotFoundError(collector_name)

    current = dict(setting.other_config) if setting.other_config else {}
    body_dict = body.model_dump(mode="json")
    for key, value in body_dict.items():
        if value is None:
            current.pop(key, None)
        else:
            current[key] = value
    await repo.update(setting.id, {"other_config": current})

    updated = await repo.get_by_name(collector_name)
    return ApiResponse.success(
        CollectorSettingResponse.model_validate(updated).model_dump()
    )


@router.post(
    "/stop/{collector_name}",
    summary="强制停止采集任务",
    description="向正在运行的采集任务发送停止信号。任务会在当前批次完成后停止。",
)
async def stop_collector(
    collector_name: Annotated[
        str,
        Path(description="采集器名称"),
    ],
):
    if collector_name not in ALL_COLLECTORS:
        raise CollectorNotFoundError(collector_name)

    stopped = CollectorService.request_stop(collector_name)
    return ApiResponse.success({
        "collector_name": collector_name,
        "stopped": stopped,
        "message": (
            "Stop signal sent" if stopped
            else "Task is not currently running"
        ),
    })


@router.get(
    "/status",
    summary="查询所有采集任务状态",
    description="返回所有采集任务的运行状态和实时进度。",
)
async def get_all_task_status():
    statuses = CollectorService.get_all_task_statuses()
    items = [
        TaskStatusResponse(
            collector_name=name,
            display_name=COLLECTOR_META.get(name, {}).get("display_name", ""),
            status=state["status"],
            progress=state["progress"],
            total=state["total"],
            message=state["message"],
            started_at=state.get("started_at"),
        ).model_dump()
        for name, state in statuses.items()
    ]
    return ApiResponse.success({"items": items})


@router.get(
    "/status/{collector_name}",
    summary="查询指定采集任务状态",
    description="返回指定采集任务的运行状态和实时进度。",
)
async def get_task_status(
    collector_name: Annotated[
        str,
        Path(description="采集器名称"),
    ],
):
    if collector_name not in ALL_COLLECTORS:
        raise CollectorNotFoundError(collector_name)

    state = CollectorService.get_task_status(collector_name)
    if state is None:
        raise CollectorNotFoundError(collector_name)

    return ApiResponse.success(
        TaskStatusResponse(
            collector_name=collector_name,
            display_name=COLLECTOR_META.get(collector_name, {}).get("display_name", ""),
            status=state["status"],
            progress=state["progress"],
            total=state["total"],
            message=state["message"],
            started_at=state.get("started_at"),
        ).model_dump()
    )


@router.get(
    "/logs",
    summary="查询采集日志",
    description="分页查询采集执行日志，支持按采集器筛选。",
)
async def list_collect_logs(
    collector: str | None = Query(
        default=None, description="采集器名称筛选"
    ),
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量"),
    session: AsyncSession = Depends(get_db),
):
    repo = CollectLogRepo(session)
    items, total = await repo.list_by_collector(
        collector_name=collector, page=page, page_size=page_size,
    )
    data = CollectLogListData(
        items=[
            CollectLogResponse(
                id=item.id,
                collector_name=item.collector_name,
                display_name=COLLECTOR_META.get(item.collector_name, {}).get("display_name", ""),
                status=item.status,
                records_added=item.records_added,
                records_updated=item.records_updated,
                error_message=item.error_message,
                duration_ms=item.duration_ms,
                started_at=item.started_at,
                finished_at=item.finished_at,
            ) for item in items
        ],
        total=total,
        page=page,
        page_size=page_size,
    )
    return ApiResponse.success(data.model_dump())


@router.delete(
    "/logs",
    summary="清空采集日志",
    description="删除所有采集执行日志记录。",
)
async def clear_collect_logs(
    session: AsyncSession = Depends(get_db),
):
    repo = CollectLogRepo(session)
    count = await repo.delete_all()
    await session.commit()
    return ApiResponse.success({"deleted": count})
