"""基金相关 Pydantic 模型."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class FundResponse(BaseModel):
    """基金基本信息响应."""

    id: UUID = Field(description="基金唯一 ID")
    code: str = Field(description="基金代码，如 000001")
    name: str = Field(description="基金名称")
    type: str | None = Field(default=None, description="基金类型：股票型/混合型/ETF 等")
    company: str | None = Field(default=None, description="基金公司名称")
    established_date: date | None = Field(default=None, description="成立日期")
    scale: Decimal | None = Field(
        default=None, description="基金规模（亿元）"
    )
    fund_manager: str | None = Field(default=None, description="基金经理")

    model_config = {"from_attributes": True}


class FundNavResponse(BaseModel):
    """基金净值响应."""

    id: UUID = Field(description="记录唯一 ID")
    fund_id: UUID = Field(description="关联基金 ID")
    date: date
    nav: Decimal | None = Field(default=None, description="单位净值")
    accumulated_nav: Decimal | None = Field(default=None, description="累计净值")
    daily_change_pct: Decimal | None = Field(
        default=None, description="日涨跌幅（%）"
    )

    model_config = {"from_attributes": True}


class FundEstimateResponse(BaseModel):
    """基金实时估值响应."""

    id: UUID = Field(description="记录唯一 ID")
    fund_id: UUID = Field(description="关联基金 ID")
    timestamp: datetime = Field(description="估值时间戳")
    estimate_nav: Decimal | None = Field(default=None, description="估算净值")
    estimate_change_pct: Decimal | None = Field(
        default=None, description="估算涨跌幅（%）"
    )
    estimate_change_amount: Decimal | None = Field(
        default=None, description="估算涨跌额"
    )

    model_config = {"from_attributes": True}


class FundListData(BaseModel):
    """基金列表响应."""

    items: list[FundResponse] = Field(description="基金列表")
    total: int = Field(description="总数")
    page: int = Field(default=1, ge=1, description="当前页码")
    page_size: int = Field(
        default=20, ge=1, le=100, description="每页数量"
    )


class FundNavListData(BaseModel):
    """基金净值列表响应."""

    items: list[FundNavResponse] = Field(description="净值列表")


class FundEstimateListData(BaseModel):
    """基金估值列表响应."""

    items: list[FundEstimateResponse] = Field(description="估值列表")
