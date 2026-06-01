"""AI Provider 管理 API 路由."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query

from app.api.deps import get_ai_provider_repo
from app.core.errors import AIProviderNotFoundError, InvalidArgumentError
from app.core.response import ApiResponse
from app.repositories.system_repo import AIProviderRepo
from app.schemas.ai import (
    AIProviderCreate,
    AIProviderListData,
    AIProviderResponse,
    AIProviderUpdate,
)

router = APIRouter(prefix="/admin/ai-providers", tags=["AI Provider"])


@router.get(
    "",
    summary="查询 AI Provider 列表",
    description="获取所有已配置的 AI Provider，可按类型筛选",
)
async def list_ai_providers(
    provider_type: str | None = Query(
        default=None,
        description="类型筛选，逗号分隔多个值，如 deepseek,openai",
    ),
    repo: AIProviderRepo = Depends(get_ai_provider_repo),
):
    types = (
        [t.strip() for t in provider_type.split(",") if t.strip()]
        if provider_type
        else None
    )
    items = await repo.list_by_types(provider_types=types)
    data = AIProviderListData(
        items=[AIProviderResponse.model_validate(p) for p in items],
        total=len(items),
    )
    return ApiResponse.success(data.model_dump())


@router.get(
    "/active",
    summary="查询当前激活的 AI Provider",
    description="返回当前 is_active=True 的 Provider",
)
async def get_active_provider(
    repo: AIProviderRepo = Depends(get_ai_provider_repo),
):
    provider = await repo.get_active()
    if provider is None:
        return ApiResponse.success(data=None, message="No active AI provider")
    return ApiResponse.success(
        AIProviderResponse.model_validate(provider).model_dump()
    )


@router.post(
    "",
    summary="创建 AI Provider",
    status_code=201,
)
async def create_ai_provider(
    body: AIProviderCreate,
    repo: AIProviderRepo = Depends(get_ai_provider_repo),
):
    import uuid as _uuid

    from app.models.system import AIProvider

    provider = AIProvider(
        name=body.name,
        provider_type=body.provider_type,
        api_key=body.api_key,
        api_base_url=body.api_base_url,
        model_name=body.model_name,
        is_active=False,
        web_search_enabled=body.web_search_enabled,
        reasoning_enabled=body.reasoning_enabled,
        extra_config=body.extra_config,
    )
    if provider.id is None:
        provider.id = _uuid.uuid4()
    repo.session.add(provider)
    await repo.session.flush()

    return ApiResponse.success(
        AIProviderResponse.model_validate(provider).model_dump(),
        status_code=201,
    )


@router.get(
    "/{provider_id}",
    summary="查询 AI Provider 详情",
)
async def get_ai_provider(
    provider_id: Annotated[
        str,
        Path(description="AI Provider UUID"),
    ],
    repo: AIProviderRepo = Depends(get_ai_provider_repo),
):
    try:
        pid = uuid.UUID(provider_id)
    except ValueError:
        raise InvalidArgumentError("AI Provider ID 格式无效")

    provider = await repo.get(pid)
    if provider is None:
        raise AIProviderNotFoundError(provider_id)
    return ApiResponse.success(
        AIProviderResponse.model_validate(provider).model_dump()
    )


@router.put(
    "/{provider_id}",
    summary="更新 AI Provider",
)
async def update_ai_provider(
    provider_id: Annotated[str, Path(description="AI Provider UUID")],
    body: AIProviderUpdate,
    repo: AIProviderRepo = Depends(get_ai_provider_repo),
):
    try:
        pid = uuid.UUID(provider_id)
    except ValueError:
        raise InvalidArgumentError("AI Provider ID 格式无效")

    provider = await repo.get(pid)
    if provider is None:
        raise AIProviderNotFoundError(provider_id)

    updates = body.model_dump(exclude_unset=True)
    if updates:
        await repo.update(pid, updates)
        await repo.session.flush()

    updated = await repo.get(pid)
    return ApiResponse.success(
        AIProviderResponse.model_validate(updated).model_dump()
    )


@router.delete(
    "/{provider_id}",
    summary="删除 AI Provider",
)
async def delete_ai_provider(
    provider_id: Annotated[str, Path(description="AI Provider UUID")],
    repo: AIProviderRepo = Depends(get_ai_provider_repo),
):
    try:
        pid = uuid.UUID(provider_id)
    except ValueError:
        raise InvalidArgumentError("AI Provider ID 格式无效")

    provider = await repo.get(pid)
    if provider is None:
        raise AIProviderNotFoundError(provider_id)

    if provider.is_active:
        raise InvalidArgumentError("无法删除当前激活的 AI Provider，请先切换激活")

    await repo.delete(pid)
    return ApiResponse.success(message="AI Provider deleted")


@router.post(
    "/{provider_id}/activate",
    summary="激活 AI Provider",
    description="切换激活到指定 Provider，自动停用其他所有 Provider",
)
async def activate_ai_provider(
    provider_id: Annotated[str, Path(description="AI Provider UUID")],
    repo: AIProviderRepo = Depends(get_ai_provider_repo),
):
    try:
        pid = uuid.UUID(provider_id)
    except ValueError:
        raise InvalidArgumentError("AI Provider ID 格式无效")

    provider = await repo.get(pid)
    if provider is None:
        raise AIProviderNotFoundError(provider_id)

    await repo.set_active(pid)
    return ApiResponse.success(
        AIProviderResponse.model_validate(await repo.get(pid)).model_dump()
    )


@router.post(
    "/{provider_id}/test",
    summary="测试 AI Provider 连通性",
    description="向 AI API 发送一条简单消息验证密钥和网络是否正常",
)
async def test_ai_provider_connection(
    provider_id: Annotated[str, Path(description="AI Provider UUID")],
    repo: AIProviderRepo = Depends(get_ai_provider_repo),
):
    try:
        pid = uuid.UUID(provider_id)
    except ValueError:
        raise InvalidArgumentError("AI Provider ID 格式无效")

    provider = await repo.get(pid)
    if provider is None:
        raise AIProviderNotFoundError(provider_id)

    from app.ai.openai_compat import OpenAICompatibleProvider

    client = OpenAICompatibleProvider(
        base_url=provider.api_base_url or "",
        api_key=provider.api_key or "",
        model=provider.model_name or "",
        provider_type=provider.provider_type,
    )
    try:
        text = await client.chat(
            messages=[{"role": "user", "content": "回复 OK 即可"}],
            temperature=0.1,
            max_tokens=10,
        )
        return ApiResponse.success({
            "success": True,
            "reply": text[:200],
        })
    except Exception as e:
        return ApiResponse.success({
            "success": False,
            "error": str(e),
        })
