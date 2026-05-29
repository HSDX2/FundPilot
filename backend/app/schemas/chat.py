"""Chat request/response schemas."""

from pydantic import BaseModel, Field


class ChatContext(BaseModel):
    """上下文信息：触发问询时所在页面的基金/板块数据."""

    fund_code: str | None = None
    fund_name: str | None = None
    sector_id: str | None = None
    sector_name: str | None = None
    web_search: bool = False


class ChatRequest(BaseModel):
    """聊天请求."""

    session_id: str | None = Field(
        default=None, description="会话 ID，为空则创建新会话",
    )
    message: str = Field(..., min_length=1, description="用户消息")
    context: ChatContext = Field(default_factory=ChatContext)
