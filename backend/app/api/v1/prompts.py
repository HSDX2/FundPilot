"""Prompt settings API routes."""

from fastapi import APIRouter, Depends

from app.api.deps import get_prompt_setting_repo
from app.core.response import ApiResponse
from app.repositories.system_repo import PromptSettingRepo

router = APIRouter(prefix="/admin/prompts", tags=["Prompt Settings"])

# 默认提示词（代码中的原始版本）
DEFAULTS: dict[str, str] = {}

def _load_defaults() -> dict[str, str]:
    """加载 prompts.py 中的默认提示词."""
    global DEFAULTS
    if DEFAULTS:
        return DEFAULTS
    from app.ai.prompts import (
        CHAT_SYSTEM,
        FUND_ADVICE_SYSTEM,
        FUND_ADVICE_USER,
        NEWS_SENTIMENT_SYSTEM,
        NEWS_SENTIMENT_USER,
        RECOMMEND_DIP_BUY_SYSTEM,
        RECOMMEND_DIP_BUY_USER,
        RECOMMEND_TOP_PICKS_SYSTEM,
        RECOMMEND_TOP_PICKS_USER,
        SECTOR_ANALYSIS_SYSTEM,
        SECTOR_ANALYSIS_USER_DAILY,
        SECTOR_ANALYSIS_USER_MONTHLY,
        SECTOR_ANALYSIS_USER_WEEKLY,
    )
    DEFAULTS = {
        "sector_analysis_system": SECTOR_ANALYSIS_SYSTEM,
        "sector_analysis_user_daily": SECTOR_ANALYSIS_USER_DAILY,
        "sector_analysis_user_weekly": SECTOR_ANALYSIS_USER_WEEKLY,
        "sector_analysis_user_monthly": SECTOR_ANALYSIS_USER_MONTHLY,
        "news_sentiment_system": NEWS_SENTIMENT_SYSTEM,
        "news_sentiment_user": NEWS_SENTIMENT_USER,
        "fund_advice_system": FUND_ADVICE_SYSTEM,
        "fund_advice_user": FUND_ADVICE_USER,
        "chat_system": CHAT_SYSTEM,
        "recommend_top_picks_system": RECOMMEND_TOP_PICKS_SYSTEM,
        "recommend_top_picks_user": RECOMMEND_TOP_PICKS_USER,
        "recommend_dip_buy_system": RECOMMEND_DIP_BUY_SYSTEM,
        "recommend_dip_buy_user": RECOMMEND_DIP_BUY_USER,
    }
    return DEFAULTS


PROMPT_LABELS: dict[str, str] = {
    "sector_analysis_system": "板块分析 — 系统提示词",
    "sector_analysis_user_daily": "板块分析 — 日报用户提示词",
    "sector_analysis_user_weekly": "板块分析 — 周报用户提示词",
    "sector_analysis_user_monthly": "板块分析 — 月报用户提示词",
    "news_sentiment_system": "新闻情绪 — 系统提示词",
    "news_sentiment_user": "新闻情绪 — 用户提示词",
    "fund_advice_system": "基金建议 — 系统提示词",
    "fund_advice_user": "基金建议 — 用户提示词",
    "chat_system": "AI 问询 — 系统提示词",
    "recommend_top_picks_system": "综合推荐 — 系统提示词",
    "recommend_top_picks_user": "综合推荐 — 用户提示词",
    "recommend_dip_buy_system": "加仓推荐 — 系统提示词",
    "recommend_dip_buy_user": "加仓推荐 — 用户提示词",
}


@router.get("", summary="获取所有提示词（含默认值）")
async def list_prompts(
    repo: PromptSettingRepo = Depends(get_prompt_setting_repo),
):
    defaults = _load_defaults()
    stored = await repo.get_all()
    items = []
    for key, default_text in defaults.items():
        items.append({
            "key": key,
            "label": PROMPT_LABELS.get(key, key),
            "default_text": default_text,
            "custom_text": stored.get(key),
        })
    return ApiResponse.success({"items": items})


@router.put("/{prompt_key}", summary="更新提示词")
async def save_prompt(
    prompt_key: str,
    body: dict,
    repo: PromptSettingRepo = Depends(get_prompt_setting_repo),
):
    text = body.get("prompt_text", "")
    await repo.upsert(prompt_key, text)
    await repo.session.commit()
    return ApiResponse.success(None, message="提示词已保存")


@router.delete("/{prompt_key}", summary="重置提示词为默认值")
async def reset_prompt(
    prompt_key: str,
    repo: PromptSettingRepo = Depends(get_prompt_setting_repo),
):
    existing = await repo.get_by_key(prompt_key)
    if existing:
        await repo.session.delete(existing)
        await repo.session.commit()
    return ApiResponse.success(None, message="已重置为默认值")
