"""Tests for APScheduler lifecycle."""

import asyncio
from unittest.mock import MagicMock

import pytest
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.tasks.scheduler import init_scheduler


class TestScheduler:
    @pytest.fixture
    def sched(self):
        """Provide a fresh, stopped scheduler for each test."""
        s = AsyncIOScheduler()
        yield s
        if s.running:
            s.shutdown(wait=False)

    def test_init_scheduler_registers_handlers(self):
        """init_scheduler should register startup/shutdown handlers."""
        app = MagicMock()
        init_scheduler(app)
        assert app.on_event.call_count == 2

    @pytest.mark.asyncio
    async def test_start_stop(self, sched):
        """Scheduler should start and stop without error."""
        sched.start()
        assert sched.running
        sched.shutdown(wait=False)
        await asyncio.sleep(0.05)
        assert not sched.running

    def test_not_running_by_default(self, sched):
        """Scheduler should not be running before start()."""
        assert not sched.running

    @pytest.mark.asyncio
    async def test_double_start_raises(self, sched):
        """Starting an already-running scheduler should raise."""
        sched.start()
        with pytest.raises(Exception):
            sched.start()
        sched.shutdown(wait=False)
