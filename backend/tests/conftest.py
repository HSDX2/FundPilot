"""Shared test fixtures and configuration.

Database-backed tests require the postgres_test container:
  docker compose --profile test up -d postgres_test
"""

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings


@pytest.fixture(scope="session")
def test_settings() -> Settings:
    return Settings(
        DB_NAME="fundpilot_test",
        DB_PORT=5433,
        LOG_LEVEL="ERROR",
        DEBUG=False,
    )


@pytest.fixture
def app() -> FastAPI:
    """Import and return the FastAPI app."""
    from app.main import app as fastapi_app
    return fastapi_app


@pytest.fixture
async def async_client(app: FastAPI) -> AsyncClient:
    """Async test client for API endpoint testing."""
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test"
    ) as client:
        yield client
