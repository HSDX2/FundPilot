"""Base classes and utilities for third-party data sources."""

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from collections.abc import Callable, Coroutine
from typing import Any

logger = logging.getLogger(__name__)


class BaseDataSource(ABC):
    """Abstract base class for third-party data sources."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique data source identifier."""
        ...

    @abstractmethod
    async def fetch(self, **kwargs) -> list[dict[str, Any]]:
        """Fetch raw data. Returns a list of dicts."""
        ...


async def with_retry(
    coro_fn: Callable[[], Coroutine[Any, Any, list[dict[str, Any]]]],
    source_name: str = "unknown",
    max_retries: int = 3,
    base_delay: float = 1.0,
) -> list[dict[str, Any]]:
    """Execute an async callable with exponential backoff retry.

    Delays: 1s → 2s → 4s before giving up.
    Returns empty list on exhaustion.
    """
    last_exc: Exception | None = None
    for attempt in range(max_retries):
        try:
            return await coro_fn()
        except Exception as exc:
            last_exc = exc
            if attempt < max_retries - 1:
                delay = base_delay * (2**attempt)
                logger.warning(
                    "%s attempt %d/%d failed: %s. Retrying in %.1fs...",
                    source_name, attempt + 1, max_retries, exc, delay,
                )
                await asyncio.sleep(delay)
    logger.error(
        "%s exhausted all %d retries: %s", source_name, max_retries, last_exc,
    )
    return []


class RateLimiter:
    """Simple async rate limiter: ensures a minimum interval between calls."""

    def __init__(self, min_interval: float = 0.5):
        self._min_interval = min_interval
        self._last_call: float = 0.0

    async def wait(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_call
        if elapsed < self._min_interval:
            await asyncio.sleep(self._min_interval - elapsed)
        self._last_call = time.monotonic()
