"""Tests for system Pydantic schemas."""

from uuid import uuid4

from app.schemas.system import (
    CollectorSettingResponse,
    CollectorSettingUpdate,
    CollectorTriggerRequest,
    CollectResultResponse,
    ScheduleConfig,
    ScheduleConfigUpdate,
)


class TestCollectorSettingResponse:
    def test_basic(self):
        data = CollectorSettingResponse(
            id=uuid4(),
            collector_name="etf",
            display_name="ETF实时采集",
            interval_seconds=30,
            is_active=True,
        )
        assert data.collector_name == "etf"
        assert data.is_active is True

    def test_required_fields(self):
        """is_active and interval_seconds are required."""
        data = CollectorSettingResponse(
            id=uuid4(),
            collector_name="test",
            interval_seconds=60,
            is_active=False,
        )
        assert data.display_name is None


class TestCollectorSettingUpdate:
    def test_basic(self):
        data = CollectorSettingUpdate(interval_seconds=60, is_active=False)
        assert data.interval_seconds == 60
        assert data.is_active is False

    def test_partial_update(self):
        data = CollectorSettingUpdate(is_active=False)
        assert data.interval_seconds is None


class TestCollectorTriggerRequest:
    def test_basic(self):
        data = CollectorTriggerRequest(collector="etf")
        assert data.collector == "etf"


class TestCollectResultResponse:
    def test_basic(self):
        data = CollectResultResponse(
            collector_name="etf",
            records_added=10,
            records_updated=5,
            errors=[],
        )
        assert data.records_added == 10
        assert data.errors == []

    def test_defaults(self):
        data = CollectResultResponse(collector_name="test")
        assert data.records_added == 0
        assert data.records_updated == 0
        assert data.errors == []


class TestScheduleConfig:
    def test_defaults(self):
        config = ScheduleConfig()
        assert config.mode == "interval"
        assert config.active_start_time is None
        assert config.active_end_time is None
        assert config.interval_minutes is None
        assert config.specific_time is None
        assert config.weekdays is None
        assert config.month_days is None

    def test_interval_mode(self):
        config = ScheduleConfig(
            mode="interval",
            interval_minutes=60,
            active_start_time="08:00:00",
            active_end_time="15:00:00",
            weekdays=[1, 2, 3, 4, 5],
        )
        assert config.mode == "interval"
        assert config.interval_minutes == 60
        assert str(config.active_start_time) == "08:00:00"
        assert config.weekdays == [1, 2, 3, 4, 5]

    def test_specific_time_mode(self):
        config = ScheduleConfig(
            mode="specific_time",
            specific_time="12:00:00",
            month_days=[1, 15],
        )
        assert config.mode == "specific_time"
        assert str(config.specific_time) == "12:00:00"
        assert config.month_days == [1, 15]

    def test_full_config(self):
        config = ScheduleConfig(
            active_start_time="08:00:00",
            active_end_time="15:00:00",
            mode="specific_time",
            specific_time="12:00:00",
            weekdays=[1, 2, 3, 4, 5],
            month_days=[1],
        )
        assert config.active_start_time is not None
        assert config.active_end_time is not None
        assert config.specific_time is not None


class TestScheduleConfigUpdate:
    def test_empty_update(self):
        update = ScheduleConfigUpdate()
        assert update.mode is None
        assert update.interval_minutes is None

    def test_partial_update(self):
        update = ScheduleConfigUpdate(
            mode="interval",
            interval_minutes=120,
            weekdays=[1, 2, 3, 4, 5],
        )
        assert update.mode == "interval"
        assert update.interval_minutes == 120
        assert update.active_start_time is None
