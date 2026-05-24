"""Tests for core configuration."""

from app.core.config import Settings


class TestSettings:
    def test_default_values(self):
        """Settings should have sensible defaults."""
        s = Settings()
        assert s.APP_NAME == "FundPilot"
        assert s.DEBUG is False
        assert s.LOG_LEVEL == "INFO"
        assert s.DB_HOST == "localhost"
        assert s.DB_PORT == 5432

    def test_database_url_property(self):
        """database_url should build correct connection string."""
        s = Settings(
            DB_USER="test_user",
            DB_PASSWORD="test_pass",
            DB_HOST="db.example.com",
            DB_PORT=15432,
            DB_NAME="test_db",
        )
        expected = (
            "postgresql+asyncpg://test_user:test_pass"
            "@db.example.com:15432/test_db"
        )
        assert s.database_url == expected

    def test_database_url_sync(self):
        """database_url_sync should build sync connection string."""
        s = Settings(
            DB_USER="user",
            DB_PASSWORD="pass",
            DB_HOST="localhost",
            DB_PORT=5432,
            DB_NAME="db",
        )
        expected = "postgresql://user:pass@localhost:5432/db"
        assert s.database_url_sync == expected

    def test_env_file_configured(self):
        """Settings should look for .env file."""
        assert ".env" in Settings.model_config.get("env_file", [])
