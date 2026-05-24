"""采集控制 API 路由."""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_collector_service,
    get_collector_setting_repo,
)
from app.core.database import get_db
from app.core.errors import CollectorNotFoundError
from app.core.response import ApiResponse
from app.repositories.system_repo import CollectLogRepo, CollectorSettingRepo
from app.schemas.system import (
    CollectLogListData,
    CollectLogResponse,
    CollectorSettingResponse,
    CollectorSettingUpdate,
    CollectorTriggerRequest,
    CollectResultResponse,
    ScheduleConfigUpdate,
    TaskStatusResponse,
)
from app.services.collector_service import ALL_COLLECTORS, CollectorService

router = APIRouter(prefix="/collect", tags=["数据采集"])


@router.post(
    "/trigger",
    summary="手动触发数据采集",
    description=(
        "手动触发指定的数据采集任务。可选采集器："
        "fund_list(基金列表) / etf_list(ETF基金列表) / "
        "etf(ETF实时行情) / sector(板块实时) / "
        "sector_list(板块列表) / sector_daily(板块每日数据) / "
        "sector_money_flow(板块资金流向) / "
        "fund_estimate(基金估值) / fund_nav(基金净值历史) / "
        "news(新闻) / market_sentiment(市场情绪)"
    ),
)
async def trigger_collect(
    body: CollectorTriggerRequest,
    service: CollectorService = Depends(get_collector_service),
):
    """手动触发指定采集器执行一次数据采集."""
    collector_map = {
        "fund_list": service.collect_fund_list,
        "etf_list": service.collect_etf_list,
        "etf": service.collect_etf_spot,
        "sector": service.collect_sector_realtime,
        "sector_list": service.collect_sector_list,
        "sector_daily": service.collect_sector_daily_all,
        "sector_money_flow": service.collect_sector_money_flow,
        "fund_estimate": service.collect_estimates,
        "fund_nav": service.collect_fund_nav_all,
        "news": service.collect_news,
        "market_sentiment": service.collect_market_sentiment,
    }

    if body.collector not in collector_map:
        raise CollectorNotFoundError(body.collector)

    if body.collector == "news":
        result = await service.collect_news(sources=body.sources)
    else:
        collector_fn = collector_map[body.collector]
        result = await collector_fn()
    return ApiResponse.success(
        CollectResultResponse(
            collector_name=body.collector,
            records_added=result.records_added,
            records_updated=result.records_updated,
            errors=result.errors,
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
    items = [
        CollectorSettingResponse.model_validate(s).model_dump()
        for s in settings
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
                "采集器名称：fund_list / etf_list / etf / sector / "
                "sector_list / sector_daily / sector_money_flow / "
                "fund_estimate / fund_nav / news / market_sentiment"
            ),
        ),
    ],
    body: CollectorSettingUpdate,
    repo: CollectorSettingRepo = Depends(get_collector_setting_repo),
):
    setting = await repo.get_by_name(collector_name)
    if setting is None:
        raise CollectorNotFoundError(collector_name)

    update_data = {}
    if body.interval_seconds is not None:
        update_data["interval_seconds"] = body.interval_seconds
    if body.is_active is not None:
        update_data["is_active"] = body.is_active

    if update_data:
        await repo.update(setting.id, update_data)

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

    current = setting.schedule_config or {}
    updates = body.model_dump(exclude_none=True)
    current.update(updates)
    await repo.update(setting.id, {"schedule_config": current})

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
        items=[CollectLogResponse.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )
    return ApiResponse.success(data.model_dump())
