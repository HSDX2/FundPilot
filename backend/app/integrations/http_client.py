"""Shared HTTP client for third-party API calls."""

from aiohttp import ClientSession, ClientTimeout


async def get_http_session() -> ClientSession:
    """Create a reusable aiohttp session with sensible defaults."""
    timeout = ClientTimeout(total=30)
    return ClientSession(timeout=timeout)
