"""推荐系统 Pydantic 模型."""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class RecommendItem(BaseModel):
    """单条推荐结果."""

    type: str = Field(description="推荐类型：fund / sector")
    action: str = Field(
        description="操作建议：buy(推荐)/add(加仓)/watch(观望)/stop(止损)",
    )
    target_id: str = Field(description="目标 ID（基金代码或板块 UUID）")
    target_name: str = Field(description="目标名称")
    target_code: str | None = Field(default=None, description="基金代码或板块代码")
    confidence: int = Field(ge=0, le=100, description="置信度 0-100")
    reason_summary: str = Field(description="推荐理由摘要")
    reason_detail: dict[str, Any] | None = Field(
        default=None, description="详细分析（技术面/基本面/情绪等）"
    )
    risk_warning: str | None = Field(default=None, description="风险提示")
    source_data: dict[str, Any] | None = Field(
        default=None, description="来源数据快照",
    )


class RecommendRequest(BaseModel):
    """推荐请求."""

    limit: int = Field(default=10, ge=1, le=20, description="推荐数量")
    category: str | None = Field(
        default=None, description="筛选：fund / sector / all（默认 all）",
    )


class DipBuyRequest(BaseModel):
    """加仓推荐请求."""

    limit: int = Field(default=10, ge=1, le=20, description="推荐数量")
    max_drawdown: float = Field(
        default=5.0, ge=1.0, le=50.0, description="最大回撤阈值（%）",
    )
    min_consecutive_days: int = Field(
        default=3, ge=1, le=20, description="最少连跌天数",
    )


class RecommendResponse(BaseModel):
    """推荐结果响应."""

    items: list[RecommendItem]
    total: int
