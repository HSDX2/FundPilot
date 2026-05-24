"""Test fixtures for API tests with dependency overrides."""

from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient


@pytest.fixture
def app() -> FastAPI:
    """Create a FastAPI test app with all DB dependencies overridden."""
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware

    from app.api.v1.router import router as v1_router
    from app.core.errors import AppError
    from app.core.response import ApiResponse

    test_app = FastAPI(title="FundPilot-Test")

    test_app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @test_app.exception_handler(AppError)
    async def app_exception_handler(request, exc):
        return ApiResponse.error(exc.code, exc.message, exc.status_code)

    @test_app.exception_handler(Exception)
    async def unhandled_exception_handler(request, exc):
        return ApiResponse.error("INTERNAL_ERROR", "Internal server error", 500)

    test_app.include_router(v1_router)

    @test_app.get("/health")
    async def health():
        return {"status": "ok"}

    return test_app


@pytest.fixture
async def async_client(app: FastAPI) -> AsyncClient:
    """Async test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test"
    ) as client:
        yield client


@pytest.fixture
def mock_session():
    """Mock database session."""
    return AsyncMock()
