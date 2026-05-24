"""系统配置相关 Pydantic 模型."""

from datetime import datetime, time
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class CollectorSettingResponse(BaseModel):
    """采集器配置响应."""

    id: UUID = Field(description="配置唯一 ID")
    collector_name: str = Field(description="采集器名称")
    display_name: str | None = Field(default=None, description="显示名称")
    interval_seconds: int = Field(description="采集间隔（秒）")
    is_active: bool = Field(description="是否启用")
    schedule_config: dict | None = Field(
        default=None, description="灵活定时配置"
    )
    last_run_at: datetime | None = Field(
        default=None, description="上次运行时间"
    )
    last_status: str | None = Field(
        default=None, description="上次运行状态"
    )

    model_config = {"from_attributes": True}


class CollectorSettingUpdate(BaseModel):
    """采集器配置更新请求."""

    interval_seconds: int | None = Field(
        default=None, ge=1, description="采集间隔（秒），最小 1 秒"
    )
    is_active: bool | None = Field(
        default=None, description="是否启用该采集器"
    )


class ScheduleConfig(BaseModel):
    """灵活定时配置。

    支持两种模式：
    - interval: 按固定间隔执行（如每 60 分钟）
    - specific_time: 在指定时间点执行（如 12:00）

    两种模式均支持激活时间窗口和日期维度约束。
    """

    active_start_time: time | None = Field(
        default=None, description="激活时间窗口开始，如 08:00",
    )
    active_end_time: time | None = Field(
        default=None, description="激活时间窗口结束，如 15:00",
    )
    mode: Literal["interval", "specific_time"] = Field(
        default="interval",
        description="定时模式：interval（间隔执行）/ specific_time（指定时刻）",
    )
    interval_minutes: int | None = Field(
        default=None, ge=1, description="间隔分钟数（mode=interval 时必填）",
    )
    specific_time: time | None = Field(
        default=None,
        description=(
            "指定执行时刻，如 12:00:00（mode=specific_time 时必填）"
        ),
    )
    weekdays: list[int] | None = Field(
        default=None,
        description="星期维度，1=周一 … 7=周日，如 [1,2,3,4,5] 表示工作日",
    )
    month_days: list[int] | None = Field(
        default=None,
        description="月日期维度，如 [1,15] 表示每月 1 号和 15 号",
    )

    @field_validator("weekdays")
    @classmethod
    def _check_weekdays(cls, v: list[int] | None) -> list[int] | None:
        if v is not None:
            for d in v:
                if not 1 <= d <= 7:
                    raise ValueError(f"weekday must be 1-7, got {d}")
        return v

    @field_validator("month_days")
    @classmethod
    def _check_month_days(cls, v: list[int] | None) -> list[int] | None:
        if v is not None:
            for d in v:
                if not 1 <= d <= 31:
                    raise ValueError(f"month_day must be 1-31, got {d}")
        return v


class ScheduleConfigUpdate(BaseModel):
    """定时配置更新请求 — 所有字段可选。"""

    active_start_time: time | None = Field(default=None, description="激活开始时间")
    active_end_time: time | None = Field(default=None, description="激活结束时间")
    mode: Literal["interval", "specific_time"] | None = Field(
        default=None, description="定时模式"
    )
    interval_minutes: int | None = Field(
        default=None, ge=1, description="间隔分钟数"
    )
    specific_time: time | None = Field(default=None, description="指定时刻")
    weekdays: list[int] | None = Field(default=None, description="星期维度")
    month_days: list[int] | None = Field(
        default=None, description="月日期维度"
    )


class CollectorTriggerRequest(BaseModel):
    """采集触发请求."""

    collector: str = Field(
        description=(
            "采集器名称：fund_list / etf_list / etf / sector / "
            "sector_list / sector_daily / sector_money_flow / "
            "fund_estimate / fund_nav / news / market_sentiment"
        )
    )
    sources: list[str] | None = Field(
        default=None,
        description=(
            "新闻源列表（仅 news 采集器生效）："
            "eastmoney / jin10 / cls / wallstreetcn。"
            "为空或 null 表示采集所有新闻源。"
        ),
    )


class CollectResultResponse(BaseModel):
    """采集结果响应."""

    collector_name: str = Field(default="", description="采集器名称")
    records_added: int = Field(default=0, description="新增记录数")
    records_updated: int = Field(default=0, description="更新记录数")
    errors: list[str] = Field(default_factory=list, description="错误信息列表")


class TaskStatusResponse(BaseModel):
    """采集任务状态响应."""

    collector_name: str = Field(description="采集器名称")
    status: str = Field(description="任务状态：idle / running / stopping")
    progress: int = Field(default=0, description="当前进度")
    total: int = Field(default=0, description="总任务量")
    message: str = Field(default="", description="状态描述")
    started_at: datetime | None = Field(
        default=None, description="任务启动时间 (UTC)"
    )


class CollectLogResponse(BaseModel):
    """采集日志响应."""

    id: UUID = Field(description="日志唯一 ID")
    collector_name: str = Field(description="采集器名称")
    status: str = Field(description="执行状态：success / failed / stopped")
    records_added: int = Field(default=0, description="新增记录数")
    records_updated: int = Field(default=0, description="更新记录数")
    error_message: str | None = Field(default=None, description="错误信息")
    duration_ms: int | None = Field(default=None, description="执行耗时（毫秒）")
    started_at: datetime | None = Field(default=None, description="开始时间")
    finished_at: datetime | None = Field(default=None, description="结束时间")

    model_config = {"from_attributes": True}


class CollectLogListData(BaseModel):
    """采集日志列表."""

    items: list[CollectLogResponse]
    total: int
    page: int
    page_size: int
