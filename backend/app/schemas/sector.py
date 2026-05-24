"""板块相关 Pydantic 模型."""

from datetime import date as date_type
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class SectorResponse(BaseModel):
    """板块基本信息响应."""

    id: UUID = Field(description="板块唯一 ID")
    name: str = Field(description="板块名称")
    code: str | None = Field(default=None, description="板块代码")
    category: str = Field(description="板块分类：industry（行业）/ concept（概念）")
    description: str | None = Field(default=None, description="板块描述")

    model_config = {"from_attributes": True}


class SectorSnapshotResponse(BaseModel):
    """板块行情快照响应."""

    id: UUID = Field(description="记录唯一 ID")
    sector_id: UUID = Field(description="关联板块 ID")
    timestamp: datetime = Field(description="快照时间")
    price: Decimal | None = Field(default=None, description="当前价格")
    open: Decimal | None = Field(default=None, description="开盘价")
    high: Decimal | None = Field(default=None, description="最高价")
    low: Decimal | None = Field(default=None, description="最低价")
    change_pct: Decimal | None = Field(default=None, description="涨跌幅（%）")
    volume: int | None = Field(default=None, description="成交量")
    turnover: Decimal | None = Field(default=None, description="成交额")

    model_config = {"from_attributes": True}


class SectorRankItem(BaseModel):
    """板块排行条目."""

    sector_id: UUID = Field(description="板块 ID")
    sector_name: str = Field(description="板块名称")
    category: str = Field(description="板块分类")
    price: Decimal | None = Field(default=None, description="当前价格")
    change_pct: Decimal | None = Field(default=None, description="涨跌幅（%）")
    timestamp: datetime | None = Field(default=None, description="行情时间")


class SectorListData(BaseModel):
    """板块列表响应."""

    items: list[SectorResponse] = Field(description="板块列表")
    total: int = Field(description="总数")
    page: int = Field(default=1, ge=1, description="当前页码")
    page_size: int = Field(
        default=20, ge=1, le=100, description="每页数量"
    )


class SectorSnapshotListData(BaseModel):
    """板块快照列表响应."""

    items: list[SectorSnapshotResponse] = Field(description="快照列表")


class SectorRankListData(BaseModel):
    """板块排行列表响应."""

    items: list[SectorRankItem] = Field(description="排行列表")


class SectorMoneyFlowResponse(BaseModel):
    """板块资金流向响应."""

    id: UUID = Field(description="记录唯一 ID")
    sector_id: UUID = Field(description="关联板块 ID")
    date: date_type = Field(description="日期")
    main_force_net_inflow: Decimal | None = Field(
        default=None, description="主力净流入（元）"
    )
    retail_net_inflow: Decimal | None = Field(
        default=None, description="散户净流入（元）"
    )
    middle_net_inflow: Decimal | None = Field(
        default=None, description="中单净流入（元）"
    )

    model_config = {"from_attributes": True}
