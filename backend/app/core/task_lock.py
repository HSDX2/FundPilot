"""Task execution lock to prevent concurrent background task runs."""

import asyncio
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class TaskLock:
    """Async task lock with status tracking."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._task_name: str = ""
        self._started_at: datetime | None = None

    async def try_acquire(self, task_name: str) -> bool:
        """Try to acquire the lock. Returns False if already locked (non-blocking).

        Safe in single-threaded asyncio: no await between locked() check and acquire().
        """
        if self._lock.locked():
            return False
        await self._lock.acquire()
        self._task_name = task_name
        self._started_at = datetime.now()
        logger.info("Task lock acquired: %s", task_name)
        return True

    def release(self) -> None:
        """Release the lock."""
        self._task_name = ""
        self._started_at = None
        if self._lock.locked():
            self._lock.release()
            logger.info("Task lock released")

    @property
    def status(self) -> dict:
        return {
            "running": self._lock.locked(),
            "task_name": self._task_name,
            "started_at": self._started_at.isoformat() if self._started_at else None,
        }


class ResourceLock:
    """Per-resource async lock manager.

    Manages a dict of asyncio.Lock instances keyed by resource identifier.
    Enables non-blocking acquire per resource (e.g. "fund:000001:all").
    """

    def __init__(self) -> None:
        self._locks: dict[str, asyncio.Lock] = {}

    def _lock_for(self, key: str) -> asyncio.Lock:
        if key not in self._locks:
            self._locks[key] = asyncio.Lock()
        return self._locks[key]

    async def try_acquire(self, key: str, task_name: str = "") -> bool:
        """Try to acquire the lock for *key*. Returns False if already locked."""
        lock = self._lock_for(key)
        if lock.locked():
            return False
        await lock.acquire()
        logger.info("Resource lock acquired: %s (%s)", key, task_name)
        return True

    def release(self, key: str) -> None:
        """Release the lock for *key*."""
        lock = self._locks.get(key)
        if lock and lock.locked():
            lock.release()
            logger.info("Resource lock released: %s", key)

    @property
    def size(self) -> int:
        return len(self._locks)


# Module-level singletons
sentiment_lock = TaskLock()
collect_lock = ResourceLock()
sector_batch_lock = TaskLock()
