"""X-API-Key authentication middleware."""

from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.config import settings

AUTH_WHITELIST = {"/health", "/docs", "/openapi.json", "/favicon.ico"}
AUTH_WHITELIST_PREFIXES = ("/docs",)


def _is_whitelisted(path: str) -> bool:
    if path in AUTH_WHITELIST:
        return True
    return any(path.startswith(p) for p in AUTH_WHITELIST_PREFIXES)


async def api_key_middleware(request: Request, call_next):
    if not settings.API_KEYS:
        return await call_next(request)

    if _is_whitelisted(request.url.path):
        return await call_next(request)

    api_key = request.headers.get("X-API-Key")
    valid_keys = {k.strip() for k in settings.API_KEYS.split(",") if k.strip()}

    if not api_key or api_key not in valid_keys:
        return JSONResponse(
            status_code=401,
            content={
                "success": False,
                "error": {
                    "code": "UNAUTHORIZED",
                    "message": "Invalid or missing API Key",
                },
            },
        )

    return await call_next(request)
