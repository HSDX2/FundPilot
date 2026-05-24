"""HTTP client for FundPilot API."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import httpx


def _load_dotenv() -> None:
    """Load .env from the cli/ directory if present."""
    env_file = Path(__file__).resolve().parent.parent / ".env"
    if not env_file.exists():
        return
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key, val = key.strip(), val.strip()
            if key and key not in os.environ:
                os.environ[key] = val


_load_dotenv()


class APIClient:
    """Lightweight HTTP wrapper around the FundPilot REST API."""

    def __init__(self, base_url: str | None = None) -> None:
        self._base_url = (
            base_url or os.getenv("FUNDPILOT_URL", "http://localhost:8000")
        ).rstrip("/")
        self._client = httpx.Client(timeout=httpx.Timeout(30.0))

    def _url(self, path: str) -> str:
        return f"{self._base_url}/api/v1{path}"

    def get(self, path: str, params: dict | None = None) -> dict[str, Any]:
        r = self._client.get(self._url(path), params=params)
        r.raise_for_status()
        return r.json()

    def post(self, path: str, body: dict | None = None) -> dict[str, Any]:
        r = self._client.post(self._url(path), json=body)
        r.raise_for_status()
        return r.json()

    def put(self, path: str, body: dict | None = None) -> dict[str, Any]:
        r = self._client.put(self._url(path), json=body)
        r.raise_for_status()
        return r.json()
