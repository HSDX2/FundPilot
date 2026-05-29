from datetime import datetime

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin
from app.utils.encryption import EncryptedText


class AIProvider(TimestampMixin, Base):
    __tablename__ = "ai_providers"

    name: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_type: Mapped[str] = mapped_column(String(32), nullable=False)
    api_key: Mapped[str | None] = mapped_column(EncryptedText)
    api_base_url: Mapped[str | None] = mapped_column(Text)
    model_name: Mapped[str | None] = mapped_column(String(64))
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    web_search_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    extra_config: Mapped[dict | None] = mapped_column(JSON, default=None)


class CollectorSetting(TimestampMixin, Base):
    __tablename__ = "collector_settings"

    collector_name: Mapped[str] = mapped_column(
        String(32), unique=True, nullable=False
    )
    display_name: Mapped[str | None] = mapped_column(String(64))
    description: Mapped[str | None] = mapped_column(String(256), default=None)
    interval_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    schedule_config: Mapped[dict | None] = mapped_column(JSON, default=None)
    other_config: Mapped[dict | None] = mapped_column(JSON, default=None)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_status: Mapped[str | None] = mapped_column(String(16))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class CollectLog(TimestampMixin, Base):
    __tablename__ = "collect_logs"

    collector_name: Mapped[str] = mapped_column(
        String(32), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="success"
    )
    records_added: Mapped[int] = mapped_column(Integer, default=0)
    records_updated: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)
    duration_ms: Mapped[int | None] = mapped_column(BigInteger)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PromptSetting(TimestampMixin, Base):
    __tablename__ = "prompt_settings"

    prompt_key: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False
    )
    prompt_text: Mapped[str] = mapped_column(Text, nullable=False)
