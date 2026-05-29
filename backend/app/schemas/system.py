"""系统配置相关 Pydantic 模型."""

from datetime import date, datetime, time
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
    other_config: dict | None = Field(
        default=None, description="额外参数配置"
    )
    description: str | None = Field(
        default=None, description="采集任务说明"
    )
    last_run_at: datetime | None = Field(
        default=None, description="上次运行时间"
    )
    last_status: str | None = Field(
        default=None, description="上次运行状态"
    )
    sort_order: int = Field(default=0, description="排序序号，升序排列")

    model_config = {"from_attributes": True}


class CollectorSettingUpdate(BaseModel):
    """采集器配置更新请求."""

    display_name: str | None = Field(
        default=None, description="显示名称"
    )
    description: str | None = Field(
        default=None, description="采集任务说明"
    )
    interval_seconds: int | None = Field(
        default=None, ge=1, description="采集间隔（秒），最小 1 秒"
    )
    is_active: bool | None = Field(
        default=None, description="是否启用该采集器"
    )
    sort_order: int | None = Field(
        default=None, ge=0, description="排序序号，升序排列"
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


class OtherConfigUpdate(BaseModel):
    """额外参数配置更新请求 — 所有字段可选。"""

    fund_type: str | None = Field(
        default=None,
        description=(
            "基金类型（fund_list）：etf / stock / mixed / index，空=全部"
        ),
    )
    sources: list[str] | None = Field(
        default=None,
        description=(
            "新闻源（news）：eastmoney / jin10 / cls / wallstreetcn"
        ),
    )
    start_date: date | None = Field(
        default=None,
        description=(
            "数据起始日期。为空默认取当天；有值时从该日期起回补所有历史数据。"
        ),
    )
    worker_count: int | None = Field(
        default=None, ge=1, le=12,
        description=(
            "多进程并发数（fund_nav_history）。默认 8，最大 12。"
            "每进程加载独立的 V8 引擎和数据库连接（约 100-200MB 内存），"
            "8 进程约需 800MB-1.6GB 空闲内存。建议根据机器内存调整，"
            "内存不足会导致系统卡顿。"
        ),
    )
    end_date: date | None = Field(
        default=None,
        description=(
            "数据结束日期。为空默认取今天。配合 start_date 限定分析时间范围。"
        ),
    )
    sentiment_concurrency: int | None = Field(
        default=None, ge=1, le=10,
        description=(
            "AI 并发数（news_sentiment）。默认 3，最大 10。"
            "控制同时调用 AI 接口的并发数，过大会触发 AI 接口频率限制。"
        ),
    )
    sentiment_limit: int | None = Field(
        default=None, ge=1, le=1000,
        description=(
            "单次分析条数上限（news_sentiment）。默认 50，最大 1000。"
            "限制单次任务处理的新闻条数上限。"
        ),
    )
    new_only: bool | None = Field(
        default=None,
        description=(
            "是否只补抽无历史数据基金（fund_nav_history）。"
            "开启后跳过已有净值的基金，仅采集 fund_navs 表无记录的基金。"
        ),
    )
    sector_new_only: bool | None = Field(
        default=None,
        description=(
            "是否仅补抽无数据板块（sector_batch_history）。"
            "开启后跳过已有快照的板块，仅采集 sector_snapshots 表无记录的板块。"
        ),
    )
    backfill_mf_detail: bool | None = Field(
        default=None,
        description=(
            "是否补充中单/散户资金流向细分（sector_batch_daily）。"
            "EM push2his 接口可能被 WAF 拦截，关闭后仅通过 THS 获取资金总额。"
        ),
    )
    recommend_limit: int | None = Field(
        default=None, ge=1, le=20,
        description=(
            "推荐条数上限（recommend_top_picks / recommend_dip_buy），默认 8"
        ),
    )
    max_drawdown: float | None = Field(
        default=None, ge=1.0, le=50.0,
        description=(
            "最大回撤阈值%（recommend_dip_buy），默认 5"
        ),
    )
    min_consecutive_days: int | None = Field(
        default=None, ge=1, le=20,
        description=(
            "最少连跌天数（recommend_dip_buy），默认 3"
        ),
    )


class CollectorTriggerRequest(BaseModel):
    """采集触发请求."""

    collector: str = Field(
        description=(
            "采集器名称：fund_list / etf / sector_list / "
            "fund_nav_history / fund_nav_daily / news / "
            "market_sentiment / sector_batch_history / sector_batch_daily / "
            "fund_estimate / sector_realtime"
        )
    )
    fund_type: str | None = Field(
        default=None,
        description=(
            "基金类型筛选（仅 fund_list 采集器生效）："
            "etf / stock / mixed / index。"
            "为空表示采集全部类型（含 ETF）。"
        ),
    )
    sources: list[str] | None = Field(
        default=None,
        description=(
            "新闻源列表（仅 news 采集器生效）："
            "eastmoney / jin10 / cls / wallstreetcn。"
            "为空或 null 表示采集所有新闻源。"
        ),
    )
    start_date: date | None = Field(
        default=None,
        description=(
            "数据起始日期。为空默认取当天；有值时从该日期起回补所有历史数据。"
            "格式：YYYY-MM-DD"
        ),
    )
    end_date: date | None = Field(
        default=None,
        description=(
            "数据结束日期（仅 news_sentiment ）。为空默认取今天。"
            "格式：YYYY-MM-DD"
        ),
    )
    sentiment_concurrency: int | None = Field(
        default=None, ge=1, le=10,
        description=(
            "AI 并发数（仅 news_sentiment ）。留空使用任务配置。"
        ),
    )
    sentiment_limit: int | None = Field(
        default=None, ge=1, le=1000,
        description=(
            "单次分析条数上限（仅 news_sentiment ）。留空使用任务配置。"
        ),
    )
    worker_count: int | None = Field(
        default=None, ge=1, le=12,
        description=(
            "多进程并发数（仅 fund_nav_history ）。留空使用任务配置。"
        ),
    )
    sector_new_only: bool | None = Field(
        default=None,
        description=(
            "是否仅补抽无数据板块（仅 sector_batch_history ）。"
            "留空则使用任务配置的 other_config 中的值。"
        ),
    )
    new_only: bool | None = Field(
        default=None,
        description=(
            "是否仅补抽无净值基金（仅 fund_nav_history ）。"
            "留空则使用任务配置的 other_config 中的值。"
        ),
    )
    backfill_mf_detail: bool | None = Field(
        default=None,
        description=(
            "是否补充中单/散户资金流向细分（仅 sector_batch_daily ）。"
            "留空则使用任务配置的 other_config 中的值。"
        ),
    )
    recommend_limit: int | None = Field(
        default=None, ge=1, le=20,
        description=(
            "推荐条数（仅 recommend_top_picks / recommend_dip_buy ）。"
            "留空使用任务配置。"
        ),
    )
    max_drawdown: float | None = Field(
        default=None, ge=1.0, le=50.0,
        description=(
            "最大回撤阈值（仅 recommend_dip_buy ）。"
            "留空使用任务配置。"
        ),
    )
    min_consecutive_days: int | None = Field(
        default=None, ge=1, le=20,
        description=(
            "最少连跌天数（仅 recommend_dip_buy ）。"
            "留空使用任务配置。"
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
    display_name: str = Field(default="", description="采集器显示名称")
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
    display_name: str = Field(default="", description="采集器显示名称")
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
