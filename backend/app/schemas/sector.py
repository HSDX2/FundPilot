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


class SectorDetailResponse(SectorResponse):
    """板块详情响应，包含行情快照和实时估算."""

    price: Decimal | None = Field(default=None, description="最新收盘价")
    change_pct: Decimal | None = Field(default=None, description="涨跌幅（%）")
    volume: int | None = Field(default=None, description="成交量（手）")
    realtime: dict | None = Field(default=None, description="实时估算 {price, change_pct, volume}")


class SectorSnapshotResponse(BaseModel):
    """板块行情快照响应."""

    id: UUID = Field(description="记录唯一 ID")
    sector_id: UUID = Field(description="关联板块 ID")
    timestamp: date_type = Field(description="快照日期")
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
    price: Decimal | None = Field(default=None, description="最新收盘价")
    change_pct: Decimal | None = Field(default=None, description="涨跌幅（%）")
    realtime_price: Decimal | None = Field(default=None, description="实时估算价")
    realtime_change_pct: Decimal | None = Field(default=None, description="实时涨跌幅（%）")
    timestamp: date_type | None = Field(default=None, description="行情日期")


class SectorListData(BaseModel):
    """板块列表响应."""

    items: list[SectorResponse] = Field(description="板块列表")
    total: int = Field(description="总数")
    page: int = Field(default=1, ge=1, description="当前页码")
    page_size: int = Field(
        default=20, ge=1, le=500, description="每页数量"
    )


class SectorSnapshotListData(BaseModel):
    """板块快照列表响应."""

    items: list[SectorSnapshotResponse] = Field(description="快照列表")


class SectorRankListData(BaseModel):
    """板块排行列表响应."""

    items: list[SectorRankItem] = Field(description="排行列表")
    total: int = Field(default=0, description="总条数")
    page: int = Field(default=1, ge=1, description="当前页码")
    page_size: int = Field(default=30, ge=1, le=200, description="每页条数")


class SectorMoneyFlowRankItem(BaseModel):
    """THS 资金流向排行条目（无 DB 关联，仅实时展示）."""

    id: str | None = Field(default=None, description="板块 UUID（匹配到 DB 记录时）")
    name: str = Field(description="板块名称")
    category: str = Field(description="板块分类：industry / concept")
    main_force_net_inflow: Decimal | None = Field(
        default=None, description="净流入（元）"
    )


class SectorMoneyFlowRankListData(BaseModel):
    """资金流向排行列表响应."""

    items: list[SectorMoneyFlowRankItem] = Field(description="排行列表")


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
