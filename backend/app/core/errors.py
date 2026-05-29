from typing import Any
from uuid import UUID


class ErrorCode:
    """Standard error codes used across the API."""

    INTERNAL_ERROR = "INTERNAL_ERROR"
    INVALID_ARGUMENT = "INVALID_ARGUMENT"
    FUND_NOT_FOUND = "FUND_NOT_FOUND"
    SECTOR_NOT_FOUND = "SECTOR_NOT_FOUND"
    NEWS_NOT_FOUND = "NEWS_NOT_FOUND"
    COLLECTOR_NOT_FOUND = "COLLECTOR_NOT_FOUND"
    COLLECTOR_BUSY = "COLLECTOR_BUSY"
    DATA_SOURCE_ERROR = "DATA_SOURCE_ERROR"
    AI_PROVIDER_NOT_FOUND = "AI_PROVIDER_NOT_FOUND"
    REPORT_NOT_FOUND = "REPORT_NOT_FOUND"
    ADVICE_NOT_FOUND = "ADVICE_NOT_FOUND"
    AI_ANALYSIS_FAILED = "AI_ANALYSIS_FAILED"
    TASK_RUNNING = "TASK_RUNNING"


# HTTP status code mapping per error code
ERROR_HTTP_STATUS: dict[str, int] = {
    ErrorCode.INTERNAL_ERROR: 500,
    ErrorCode.INVALID_ARGUMENT: 400,
    ErrorCode.FUND_NOT_FOUND: 404,
    ErrorCode.SECTOR_NOT_FOUND: 404,
    ErrorCode.NEWS_NOT_FOUND: 404,
    ErrorCode.COLLECTOR_NOT_FOUND: 404,
    ErrorCode.COLLECTOR_BUSY: 409,
    ErrorCode.DATA_SOURCE_ERROR: 502,
    ErrorCode.AI_PROVIDER_NOT_FOUND: 404,
    ErrorCode.REPORT_NOT_FOUND: 404,
    ErrorCode.ADVICE_NOT_FOUND: 404,
    ErrorCode.AI_ANALYSIS_FAILED: 500,
    ErrorCode.TASK_RUNNING: 409,
}


class AppError(Exception):
    """Base application exception with structured error info."""

    def __init__(
        self,
        code: str = ErrorCode.INTERNAL_ERROR,
        message: str = "Internal error",
        status_code: int | None = None,
        data: Any = None,
    ):
        self.code = code
        self.message = message
        self.status_code = status_code or ERROR_HTTP_STATUS.get(code, 500)
        self.data = data
        super().__init__(self.message)


class FundNotFoundError(AppError):
    def __init__(self, fund_code: str):
        super().__init__(
            code=ErrorCode.FUND_NOT_FOUND,
            message=f"Fund {fund_code} not found",
        )


class SectorNotFoundError(AppError):
    def __init__(self, sector_id: str | UUID):
        super().__init__(
            code=ErrorCode.SECTOR_NOT_FOUND,
            message=f"Sector {sector_id} not found",
        )


class NewsNotFoundError(AppError):
    def __init__(self, news_id: str):
        super().__init__(
            code=ErrorCode.NEWS_NOT_FOUND,
            message=f"News article {news_id} not found",
        )


class CollectorNotFoundError(AppError):
    def __init__(self, name: str):
        super().__init__(
            code=ErrorCode.COLLECTOR_NOT_FOUND,
            message=f"Collector '{name}' not found",
        )


class CollectorBusyError(AppError):
    def __init__(self, name: str):
        super().__init__(
            code=ErrorCode.COLLECTOR_BUSY,
            message=f"Collector '{name}' is already running",
        )


class InvalidArgumentError(AppError):
    def __init__(self, message: str):
        super().__init__(
            code=ErrorCode.INVALID_ARGUMENT,
            message=message,
        )


class AIProviderNotFoundError(AppError):
    def __init__(self, provider_id: str | UUID):
        super().__init__(
            code=ErrorCode.AI_PROVIDER_NOT_FOUND,
            message=f"AI provider {provider_id} not found",
        )


class DataSourceError(AppError):
    def __init__(self, source: str, detail: str = ""):
        super().__init__(
            code=ErrorCode.DATA_SOURCE_ERROR,
            message=f"Data source '{source}' error: {detail}",
            status_code=502,
        )


def error_response(
    code: str,
    message: str,
    data: Any = None,
) -> dict[str, Any]:
    """Build the standard error response body."""
    body: dict[str, Any] = {
        "success": False,
        "error": {
            "code": code,
            "message": message,
        },
    }
    if data is not None:
        body["error"]["data"] = data
    return body
