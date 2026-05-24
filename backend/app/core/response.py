"""Unified API response helpers with UUID-aware JSON encoding."""

import json
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi.responses import JSONResponse

from app.core.errors import ErrorCode, error_response


class ApiJSONResponse(JSONResponse):
    """JSONResponse that handles UUID and Decimal serialization."""

    def render(self, content: Any) -> bytes:
        def _serialize(o: Any) -> str:
            if isinstance(o, UUID):
                return str(o)
            if isinstance(o, Decimal):
                return str(o)
            if isinstance(o, datetime):
                return o.isoformat()
            if isinstance(o, date):
                return o.isoformat()
            if isinstance(o, time):
                return o.isoformat()
            raise TypeError(
                f"Object of type {type(o).__name__} is not JSON serializable"
            )
        return json.dumps(
            content,
            default=_serialize,
            ensure_ascii=False,
        ).encode("utf-8")


class ApiResponse:
    """Unified API response helpers."""

    @staticmethod
    def success(
        data: Any = None,
        message: str = "",
        status_code: int = 200,
    ) -> JSONResponse:
        body: dict[str, Any] = {
            "success": True,
            "data": data,
            "message": message,
        }
        return ApiJSONResponse(content=body, status_code=status_code)

    @staticmethod
    def error(
        code: ErrorCode,
        message: str,
        status_code: int = 400,
        data: Any = None,
    ) -> JSONResponse:
        body = error_response(code, message, data)
        return ApiJSONResponse(content=body, status_code=status_code)
