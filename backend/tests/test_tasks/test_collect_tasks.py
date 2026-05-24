"""Tests for scheduled collection tasks."""

from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

from app.tasks.collect_tasks import (
    _evaluate_schedule,
    _parse_time,
    _read_news_sources,
    _should_run,
    is_in_trading_session,
    is_trading_day,
)


class TestIsInTradingSession:
    def test_morning_session(self, mocker):
        """9:30-11:30 should be trading session."""
        mock_now = datetime(2026, 5, 23, 10, 0, 0)  # 10:00 AM
        mocker.patch(
            "app.tasks.collect_tasks.datetime"
        ).now.return_value = mock_now
        assert is_in_trading_session() is True

    def test_afternoon_session(self, mocker):
        """13:00-15:00 should be trading session."""
        mock_now = datetime(2026, 5, 23, 14, 0, 0)  # 2:00 PM
        mocker.patch(
            "app.tasks.collect_tasks.datetime"
        ).now.return_value = mock_now
        assert is_in_trading_session() is True

    def test_lunch_break(self, mocker):
        """11:30-13:00 should NOT be trading session."""
        mock_now = datetime(2026, 5, 23, 12, 0, 0)
        mocker.patch(
            "app.tasks.collect_tasks.datetime"
        ).now.return_value = mock_now
        assert is_in_trading_session() is False

    def test_before_market_open(self, mocker):
        """Before 9:30 should NOT be trading session."""
        mock_now = datetime(2026, 5, 23, 9, 0, 0)
        mocker.patch(
            "app.tasks.collect_tasks.datetime"
        ).now.return_value = mock_now
        assert is_in_trading_session() is False

    def test_after_market_close(self, mocker):
        """After 15:00 should NOT be trading session."""
        mock_now = datetime(2026, 5, 23, 15, 30, 0)
        mocker.patch(
            "app.tasks.collect_tasks.datetime"
        ).now.return_value = mock_now
        assert is_in_trading_session() is False

    def test_exactly_930(self, mocker):
        """9:30 exactly should be trading session."""
        mock_now = datetime(2026, 5, 23, 9, 30, 0)
        mocker.patch(
            "app.tasks.collect_tasks.datetime"
        ).now.return_value = mock_now
        assert is_in_trading_session() is True

    def test_exactly_1500(self, mocker):
        """15:00 exactly should be trading session."""
        mock_now = datetime(2026, 5, 23, 15, 0, 0)
        mocker.patch(
            "app.tasks.collect_tasks.datetime"
        ).now.return_value = mock_now
        assert is_in_trading_session() is True


class TestIsTradingDay:
    def test_weekday(self, mocker):
        """Monday-Friday should be trading days."""
        mock_now = datetime(2026, 5, 25, 10, 0, 0)  # Monday
        mocker.patch(
            "app.tasks.collect_tasks.datetime"
        ).now.return_value = mock_now
        assert is_trading_day() is True

    def test_saturday(self, mocker):
        """Saturday should NOT be trading day."""
        mock_now = datetime(2026, 5, 23, 10, 0, 0)  # Saturday
        mocker.patch(
            "app.tasks.collect_tasks.datetime"
        ).now.return_value = mock_now
        assert is_trading_day() is False

    def test_sunday(self, mocker):
        """Sunday should NOT be trading day."""
        mock_now = datetime(2026, 5, 24, 10, 0, 0)  # Sunday
        mocker.patch(
            "app.tasks.collect_tasks.datetime"
        ).now.return_value = mock_now
        assert is_trading_day() is False


class TestShouldRun:
    @pytest.mark.asyncio
    async def test_active_setting_returns_true(self):
        """When collector is active, _should_run returns True."""
        mock_setting = AsyncMock()
        mock_setting.is_active = True
        mock_setting.schedule_config = None

        mock_repo = AsyncMock()
        mock_repo.get_by_name.return_value = mock_setting

        with patch(
            "app.tasks.collect_tasks.CollectorSettingRepo",
            return_value=mock_repo,
        ):
            with patch(
                "app.tasks.collect_tasks.async_session_factory"
            ) as mock_sf:
                mock_session = AsyncMock()
                mock_sf.return_value.__aenter__.return_value = mock_session
                result = await _should_run("etf")
                assert result is True

    @pytest.mark.asyncio
    async def test_inactive_setting_returns_false(self):
        """When collector is inactive, _should_run returns False."""
        mock_setting = AsyncMock()
        mock_setting.is_active = False

        mock_repo = AsyncMock()
        mock_repo.get_by_name.return_value = mock_setting

        with patch(
            "app.tasks.collect_tasks.CollectorSettingRepo",
            return_value=mock_repo,
        ):
            with patch(
                "app.tasks.collect_tasks.async_session_factory"
            ) as mock_sf:
                mock_session = AsyncMock()
                mock_sf.return_value.__aenter__.return_value = mock_session
                result = await _should_run("etf")
                assert result is False

    @pytest.mark.asyncio
    async def test_missing_setting_returns_false(self):
        """When collector setting doesn't exist, _should_run returns False."""
        mock_repo = AsyncMock()
        mock_repo.get_by_name.return_value = None

        with patch(
            "app.tasks.collect_tasks.CollectorSettingRepo",
            return_value=mock_repo,
        ):
            with patch(
                "app.tasks.collect_tasks.async_session_factory"
            ) as mock_sf:
                mock_session = AsyncMock()
                mock_sf.return_value.__aenter__.return_value = mock_session
                result = await _should_run("nonexistent")
                assert result is False

    @pytest.mark.asyncio
    async def test_schedule_config_disabled(self):
        """schedule_config with active window not matching now returns False."""
        mock_setting = AsyncMock()
        mock_setting.is_active = True
        # Active window 01:00-02:00 won't match current time
        mock_setting.schedule_config = {
            "active_start_time": "01:00:00",
            "active_end_time": "02:00:00",
        }

        mock_repo = AsyncMock()
        mock_repo.get_by_name.return_value = mock_setting

        with patch(
            "app.tasks.collect_tasks.CollectorSettingRepo",
            return_value=mock_repo,
        ):
            with patch(
                "app.tasks.collect_tasks.async_session_factory"
            ) as mock_sf:
                mock_session = AsyncMock()
                mock_sf.return_value.__aenter__.return_value = mock_session
                result = await _should_run("etf")
                assert result is False


class TestEvaluateSchedule:
    def test_no_config_returns_true(self):
        """Empty config should allow execution."""
        assert _evaluate_schedule({}) is True

    def test_active_window_inside(self, mocker):
        """Within active window should return True."""
        mock_now = datetime(2026, 5, 25, 10, 0, 0)  # Monday 10:00
        mocker.patch(
            "app.tasks.collect_tasks.datetime"
        ).now.return_value = mock_now
        config = {
            "active_start_time": "08:00:00",
            "active_end_time": "15:00:00",
        }
        assert _evaluate_schedule(config) is True

    def test_active_window_outside(self, mocker):
        """Outside active window should return False."""
        mock_now = datetime(2026, 5, 25, 16, 0, 0)  # Monday 16:00
        mocker.patch(
            "app.tasks.collect_tasks.datetime"
        ).now.return_value = mock_now
        config = {
            "active_start_time": "08:00:00",
            "active_end_time": "15:00:00",
        }
        assert _evaluate_schedule(config) is False

    def test_weekday_match(self, mocker):
        """Matching weekday should return True."""
        mock_now = datetime(2026, 5, 25, 10, 0, 0)  # Monday (isoweekday=1)
        mocker.patch(
            "app.tasks.collect_tasks.datetime"
        ).now.return_value = mock_now
        config = {"weekdays": [1, 2, 3, 4, 5]}
        assert _evaluate_schedule(config) is True

    def test_weekday_no_match(self, mocker):
        """Non-matching weekday should return False."""
        mock_now = datetime(2026, 5, 23, 10, 0, 0)  # Saturday (isoweekday=6)
        mocker.patch(
            "app.tasks.collect_tasks.datetime"
        ).now.return_value = mock_now
        config = {"weekdays": [1, 2, 3, 4, 5]}
        assert _evaluate_schedule(config) is False

    def test_month_day_match(self, mocker):
        """Matching month day should return True."""
        mock_now = datetime(2026, 5, 1, 10, 0, 0)  # May 1st
        mocker.patch(
            "app.tasks.collect_tasks.datetime"
        ).now.return_value = mock_now
        config = {"month_days": [1, 15]}
        assert _evaluate_schedule(config) is True

    def test_month_day_no_match(self, mocker):
        """Non-matching month day should return False."""
        mock_now = datetime(2026, 5, 10, 10, 0, 0)  # May 10th
        mocker.patch(
            "app.tasks.collect_tasks.datetime"
        ).now.return_value = mock_now
        config = {"month_days": [1, 15]}
        assert _evaluate_schedule(config) is False

    def test_all_conditions_match(self, mocker):
        """All conditions matching should return True."""
        mock_now = datetime(2026, 5, 25, 10, 0, 0)  # Mon 10:00, May 25
        mocker.patch(
            "app.tasks.collect_tasks.datetime"
        ).now.return_value = mock_now
        config = {
            "active_start_time": "08:00:00",
            "active_end_time": "15:00:00",
            "weekdays": [1, 2, 3, 4, 5],
            "month_days": list(range(1, 32)),
        }
        assert _evaluate_schedule(config) is True

    def test_ignores_sources_key(self, mocker):
        """sources key in schedule_config should not affect timing eval."""
        mock_now = datetime(2026, 5, 25, 10, 0, 0)  # Monday 10:00
        mocker.patch(
            "app.tasks.collect_tasks.datetime"
        ).now.return_value = mock_now
        config = {
            "active_start_time": "08:00:00",
            "active_end_time": "15:00:00",
            "sources": ["eastmoney", "jin10"],
        }
        assert _evaluate_schedule(config) is True


class TestParseTime:
    def test_time_object(self):
        from datetime import time
        t = time(12, 30, 0)
        result = _parse_time(t)
        assert result == t

    def test_string_full(self):
        result = _parse_time("12:30:45")
        assert result.hour == 12
        assert result.minute == 30
        assert result.second == 45

    def test_string_hm(self):
        result = _parse_time("08:00")
        assert result.hour == 8
        assert result.minute == 0
        assert result.second == 0

    def test_invalid_string(self):
        assert _parse_time("abc") is None

    def test_none(self):
        assert _parse_time(None) is None


class TestReadNewsSources:
    @pytest.mark.asyncio
    async def test_sources_in_config(self):
        """schedule_config with sources list should return it."""
        from unittest.mock import AsyncMock, MagicMock, patch

        mock_setting = MagicMock()
        mock_setting.schedule_config = {"sources": ["eastmoney", "jin10"]}

        mock_repo = AsyncMock()
        mock_repo.get_by_name.return_value = mock_setting

        with patch(
            "app.tasks.collect_tasks.CollectorSettingRepo",
            return_value=mock_repo,
        ):
            with patch(
                "app.tasks.collect_tasks.async_session_factory"
            ) as mock_sf:
                mock_session = AsyncMock()
                mock_sf.return_value.__aenter__.return_value = mock_session
                result = await _read_news_sources()
                assert result == ["eastmoney", "jin10"]

    @pytest.mark.asyncio
    async def test_no_sources_in_config(self):
        """schedule_config without sources key should return None."""
        from unittest.mock import AsyncMock, MagicMock, patch

        mock_setting = MagicMock()
        mock_setting.schedule_config = {"interval_minutes": 30}

        mock_repo = AsyncMock()
        mock_repo.get_by_name.return_value = mock_setting

        with patch(
            "app.tasks.collect_tasks.CollectorSettingRepo",
            return_value=mock_repo,
        ):
            with patch(
                "app.tasks.collect_tasks.async_session_factory"
            ) as mock_sf:
                mock_session = AsyncMock()
                mock_sf.return_value.__aenter__.return_value = mock_session
                result = await _read_news_sources()
                assert result is None

    @pytest.mark.asyncio
    async def test_no_schedule_config(self):
        """No schedule_config at all should return None."""
        from unittest.mock import AsyncMock, MagicMock, patch

        mock_setting = MagicMock()
        mock_setting.schedule_config = None

        mock_repo = AsyncMock()
        mock_repo.get_by_name.return_value = mock_setting

        with patch(
            "app.tasks.collect_tasks.CollectorSettingRepo",
            return_value=mock_repo,
        ):
            with patch(
                "app.tasks.collect_tasks.async_session_factory"
            ) as mock_sf:
                mock_session = AsyncMock()
                mock_sf.return_value.__aenter__.return_value = mock_session
                result = await _read_news_sources()
                assert result is None

    @pytest.mark.asyncio
    async def test_no_setting(self):
        """Missing collector setting should return None."""
        from unittest.mock import AsyncMock, patch

        mock_repo = AsyncMock()
        mock_repo.get_by_name.return_value = None

        with patch(
            "app.tasks.collect_tasks.CollectorSettingRepo",
            return_value=mock_repo,
        ):
            with patch(
                "app.tasks.collect_tasks.async_session_factory"
            ) as mock_sf:
                mock_session = AsyncMock()
                mock_sf.return_value.__aenter__.return_value = mock_session
                result = await _read_news_sources()
                assert result is None
