from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Server
    APP_NAME: str = "FundPilot"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # CORS
    CORS_ORIGINS: str = "*"

    # Database
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_USER: str = "fundpilot"
    DB_PASSWORD: str = ""
    DB_NAME: str = "fundpilot"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    @property
    def database_url_sync(self) -> str:
        """Synchronous URL for Alembic or admin tools."""
        return (
            f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    # AI API keys (optional, Phase 3)
    OPENAI_API_KEY: str = ""
    OPENAI_API_BASE: str = ""
    CLAUDE_API_KEY: str = ""

    # PyPI mirror (used by Dockerfile)
    PIP_INDEX_URL: str = "https://pypi.tuna.tsinghua.edu.cn/simple"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
