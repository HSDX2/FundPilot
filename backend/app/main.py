"""FastAPI application entry point."""

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.v1.router import router as v1_router
from app.core.auth import api_key_middleware
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

# API Key 认证中间件
app.middleware("http")(api_key_middleware)

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
    # macOS SSL 证书路径修正（certifi 提供的 CA bundle）
    import certifi, os as _os
    if "SSL_CERT_FILE" not in _os.environ and "REQUESTS_CA_BUNDLE" not in _os.environ:
        _os.environ["SSL_CERT_FILE"] = certifi.where()
        _os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()

    from app.integrations.akshare import force_ipv4

    force_ipv4()

    from app.core.database import engine

    # 数据库建表和初始数据改为 scripts/db/ 下的独立脚本管理：
    #   ./scripts/db/create.sh  → schema.sql  → 建表
    #   ./scripts/db/seed.sh    → seed.sql    → 初始数据
    # 启动时只做连接测试
    async with engine.begin() as conn:
        await conn.execute(text("SELECT 1"))

    logger.info("Database engine ready (schema/seed via scripts/db/)")

    # Check encryption key for AI provider API keys
    if not settings.ENCRYPTION_KEY:
        logger.warning(
            "ENCRYPTION_KEY is not set — AI provider API keys will be "
            "stored in plaintext. Set ENCRYPTION_KEY in .env for production."
        )

    # Start scheduler
    from app.tasks.scheduler import register_jobs, scheduler

    await register_jobs()
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
