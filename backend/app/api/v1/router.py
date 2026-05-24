"""Aggregate all v1 API routes."""

from fastapi import APIRouter

from app.api.v1.ai_providers import router as ai_providers_router
from app.api.v1.analysis import router as analysis_router
from app.api.v1.collect import router as collect_router
from app.api.v1.funds import router as funds_router
from app.api.v1.news import router as news_router
from app.api.v1.realtime import router as realtime_router
from app.api.v1.sectors import router as sectors_router

router = APIRouter(prefix="/api/v1")

router.include_router(funds_router)
router.include_router(sectors_router)
router.include_router(news_router)
router.include_router(realtime_router)
router.include_router(collect_router)
router.include_router(ai_providers_router)
router.include_router(analysis_router)
