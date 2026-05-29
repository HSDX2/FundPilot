"""AI 问询聊天 API — SSE 流式响应."""

import json
import logging

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_fund_repo,
    get_news_article_repo,
    get_sector_repo,
    get_sector_snapshot_repo,
    get_prompt_setting_repo,
)
from app.core.database import get_db
from app.core.response import ApiResponse
from app.repositories.fund_repo import FundNavRepo, FundRepo
from app.repositories.news_repo import NewsArticleRepo
from app.repositories.sector_repo import SectorRepo, SectorSnapshotRepo
from app.repositories.system_repo import AIProviderRepo, PromptSettingRepo
from app.repositories.watchlist_repo import WatchedFundRepo
from app.schemas.chat import ChatRequest
from app.services.chat_service import ChatService
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["AI 问询"])


async def get_chat_service(session: AsyncSession = Depends(get_db)) -> ChatService:
    return ChatService(
        ai_provider_repo=AIProviderRepo(session),
        prompt_repo=PromptSettingRepo(session),
        fund_repo=FundRepo(session),
        fund_nav_repo=FundNavRepo(session),
        sector_repo=SectorRepo(session),
        sector_snapshot_repo=SectorSnapshotRepo(session),
        news_repo=NewsArticleRepo(session),
        watchlist_repo=WatchedFundRepo(session),
    )


@router.post("", summary="AI 问询（流式）")
async def chat(body: ChatRequest, svc: ChatService = Depends(get_chat_service)):
    """发送消息给 AI 助手，返回 SSE 流式响应。"""

    async def event_stream():
        async for event in svc.chat_stream(
            session_id=body.session_id,
            message=body.message,
            context=body.context,
        ):
            yield event

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.delete("/{session_id}", summary="销毁会话")
async def destroy_session(session_id: str):
    ChatService.destroy_session(session_id)
    return ApiResponse.success(None, message="会话已销毁")
