"""AI Provider 相关 Pydantic 模型."""

from uuid import UUID

from pydantic import BaseModel, Field


class AIProviderCreate(BaseModel):
    """创建 AI Provider 请求."""

    name: str = Field(description="厂商显示名，如 DeepSeek")
    provider_type: str = Field(
        description=(
            "provider_type: deepseek / glm / qwen / openai / "
            "kimi / minimax / custom"
        )
    )
    api_key: str = Field(min_length=1, description="API 密钥")
    api_base_url: str = Field(min_length=1, description="API endpoint URL")
    web_search_enabled: bool = Field(
        default=False, description="是否启用联网搜索",
    )
    model_name: str = Field(min_length=1, description="默认模型名，如 deepseek-chat")
    extra_config: dict | None = Field(
        default=None,
        description="额外参数：max_tokens, temperature, top_p 默认值",
    )


class AIProviderUpdate(BaseModel):
    """更新 AI Provider 请求 — 所有字段可选."""

    name: str | None = Field(default=None, description="厂商显示名")
    api_key: str | None = Field(default=None, min_length=1, description="API 密钥")
    api_base_url: str | None = Field(
        default=None, min_length=1, description="API endpoint URL"
    )
    model_name: str | None = Field(
        default=None, min_length=1, description="默认模型名"
    )
    extra_config: dict | None = Field(
        default=None, description="额外参数"
    )
    web_search_enabled: bool | None = Field(
        default=None, description="是否启用联网搜索",
    )


class AIProviderResponse(BaseModel):
    """AI Provider 响应."""

    id: UUID = Field(description="Provider 唯一 ID")
    name: str = Field(description="厂商显示名")
    provider_type: str = Field(description="provider_type")
    api_base_url: str | None = Field(default=None, description="API endpoint URL")
    model_name: str | None = Field(default=None, description="默认模型名")
    is_active: bool = Field(default=False, description="是否为当前激活")
    web_search_enabled: bool = Field(default=False, description="是否启用联网搜索")
    extra_config: dict | None = Field(default=None, description="额外参数")

    model_config = {"from_attributes": True}


class AIProviderListData(BaseModel):
    """AI Provider 列表."""

    items: list[AIProviderResponse]
    total: int
