"""关注列表相关 Pydantic 模型."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class WatchedFundResponse(BaseModel):
    """关注基金响应（含基金基本信息）."""

    id: UUID = Field(description="关注记录 ID")
    fund_id: UUID = Field(description="基金 ID")
    fund_code: str = Field(description="基金代码")
    fund_name: str = Field(description="基金名称")
    fund_type: str | None = Field(default=None, description="基金类型")
    estimate_nav: Decimal | None = Field(default=None, description="盘中估值")
    estimate_change_pct: Decimal | None = Field(default=None, description="估算涨跌幅")
    holding_shares: Decimal | None = Field(default=None, description="持仓份额")
    added_at: datetime = Field(description="添加时间")

    model_config = {"from_attributes": True}


class UpdateWatchedFundRequest(BaseModel):
    """更新关注基金请求."""

    holding_shares: Decimal | None = Field(default=None, description="持仓份额")


class WatchedSectorResponse(BaseModel):
    """关注板块响应（含板块基本信息）."""

    id: UUID = Field(description="关注记录 ID")
    sector_id: UUID = Field(description="板块 ID")
    sector_name: str = Field(description="板块名称")
    sector_category: str = Field(description="板块分类")
    added_at: datetime = Field(description="添加时间")

    model_config = {"from_attributes": True}


class WatchlistData(BaseModel):
    """关注列表响应."""

    items: list = Field(description="关注列表")
    total: int = Field(description="总数")
