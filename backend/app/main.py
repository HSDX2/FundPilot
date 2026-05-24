"""FastAPI application entry point."""

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import router as v1_router
from app.core.config import settings
from app.core.errors import AppError
from app.core.response import ApiResponse

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)

app = FastAPI(
    title="FundPilot - 基金投研系统",
    description="基金预测与推荐系统，提供基金数据、板块行情和 AI 分析服务",
    version="0.1.0",
)

# CORS 跨域配置
cors_origins = [
    o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(AppError)
async def app_exception_handler(request: Request, exc: AppError):
    logger.warning(
        "AppError: code=%s message=%s", exc.code, exc.message
    )
    return ApiResponse.error(exc.code, exc.message, exc.status_code)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception: %s", exc)
    return ApiResponse.error(
        "INTERNAL_ERROR",
        "Internal server error",
        status_code=500,
    )


# 健康检查
@app.get("/health", tags=["系统"], summary="健康检查")
async def health():
    """返回服务运行状态."""
    return {"status": "ok"}


# Register routes
app.include_router(v1_router)


@app.on_event("startup")
async def startup():
    """Initialize database, scheduler, and default data on startup."""
    from app.core.database import engine
    from app.models.base import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    logger.info("Database tables created successfully")

    # Initialize default collector settings
    from app.core.constants import (
        DEFAULT_COLLECTOR_INTERVALS,
        CollectorName,
    )
    from app.core.database import async_session_factory
    from app.repositories.system_repo import CollectorSettingRepo

    defaults: dict[str, int] = {}
    for name in CollectorName:
        if name in DEFAULT_COLLECTOR_INTERVALS:
            defaults[name.value] = DEFAULT_COLLECTOR_INTERVALS[name]

    async with async_session_factory() as session:
        repo = CollectorSettingRepo(session)
        await repo.initialize_defaults(defaults)
        await session.commit()

    logger.info("Default collector settings initialized")

    # Start scheduler
    from app.tasks.scheduler import register_jobs, scheduler

    register_jobs()
    scheduler.start()
    logger.info("APScheduler started")


@app.on_event("shutdown")
async def shutdown():
    """Clean up resources on shutdown."""
    from app.core.database import engine
    from app.tasks.scheduler import scheduler

    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("APScheduler shut down")

    await engine.dispose()
    logger.info("Database engine disposed")
