"""Analysis-related Pydantic schemas."""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field


class AnalysisReportResponse(BaseModel):
    id: UUID
    date: date
    report_type: str
    content: dict
    ai_model: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AnalysisReportListData(BaseModel):
    items: list[AnalysisReportResponse]
    total: int
    page: int = 1
    page_size: int = 20


class GenerateReportRequest(BaseModel):
    sector_id: UUID = Field(description="板块 ID")
    report_type: str = Field(
        default="daily",
        description="报告类型: daily / weekly / monthly",
    )


class GenerateAllReportsRequest(BaseModel):
    report_type: str = Field(
        default="daily",
        description="报告类型: daily / weekly / monthly",
    )
    limit: int = Field(
        default=10,
        ge=1,
        le=50,
        description="分析的板块数量上限",
    )


class FundAdviceResponse(BaseModel):
    id: UUID
    fund_id: UUID
    date: date
    action: str
    reason: dict
    confidence: float | None = None
    ai_model: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class FundAdviceListData(BaseModel):
    items: list[FundAdviceResponse]
    total: int
    page: int = 1
    page_size: int = 20


class GenerateAdviceRequest(BaseModel):
    fund_id: UUID = Field(description="基金 ID")


class BatchGenerateAdviceRequest(BaseModel):
    fund_ids: list[UUID] = Field(
        min_length=1,
        max_length=20,
        description="基金 ID 列表",
    )


class SentimentResult(BaseModel):
    news_id: UUID
    sentiment_score: float | None = None
    success: bool = True


class NewsSentimentResponse(BaseModel):
    processed: int = Field(description="已处理的新闻数量")
    results: list[SentimentResult] = []


class BatchSentimentRequest(BaseModel):
    limit: int = Field(
        default=20,
        ge=1,
        le=100,
        description="最多分析 N 条新闻",
    )


# ── Market Sentiment ───────────────────────────────────────────────────

class MarketSentimentResponse(BaseModel):
    id: UUID
    date: date
    limit_up_count: int | None = None
    limit_down_count: int | None = None
    limit_up_broken_count: int | None = None
    consecutive_limit_up_count: int | None = None
    north_bound_net_inflow: float | None = None
    margin_balance_sse: float | None = None
    margin_balance_szse: float | None = None
    lhb_stock_count: int | None = None
    advance_count: int | None = None
    decline_count: int | None = None
    market_total_cap: float | None = None
    composite_sentiment_score: float | None = None
    extra: dict | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class MarketSentimentListData(BaseModel):
    items: list[MarketSentimentResponse]
    total: int
    page: int = 1
    page_size: int = 20
