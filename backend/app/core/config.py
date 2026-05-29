import os

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

    # API Key authentication (comma-separated, empty = no auth)
    API_KEYS: str = ""

    # Encryption key for sensitive data (AI provider API keys)
    # Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    ENCRYPTION_KEY: str = ""

    # Proxy bypass for Chinese financial data sources
    NO_PROXY: str = (
        "eastmoney.com,10jqka.com.cn,sina.com.cn,cls.cn,jin10.com,"
        "wallstreetcn.com,sse.com.cn,szse.cn,csindex.com.cn"
    )

    # PyPI mirror (used by Dockerfile)
    PIP_INDEX_URL: str = "https://pypi.tuna.tsinghua.edu.cn/simple"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()

# Bypass macOS system proxy for domestic financial data sources.
# macOS SystemConfiguration proxy settings are read by urllib at a lower level
# than env vars. Setting no_proxy=* tells urllib to skip proxy for all hosts.
_no_proxy = settings.NO_PROXY
if _no_proxy:
    os.environ["no_proxy"] = _no_proxy
    os.environ["NO_PROXY"] = _no_proxy
