"""Tests for APIClient."""

from __future__ import annotations

import httpx
import pytest

from fundpilot.client import APIClient


class TestAPIClient:
    def test_default_base_url(self) -> None:
        client = APIClient()
        assert client._base_url == "http://localhost:8000"

    def test_custom_base_url(self) -> None:
        client = APIClient(base_url="http://api.example.com:8080")
        assert client._base_url == "http://api.example.com:8080"

    def test_strips_trailing_slash(self) -> None:
        client = APIClient(base_url="http://api.example.com/")
        assert client._base_url == "http://api.example.com"

    def test_url_construction(self) -> None:
        client = APIClient(base_url="http://localhost:8000")
        assert client._url("/funds") == "http://localhost:8000/api/v1/funds"
        assert client._url("/sectors/rank/current") == "http://localhost:8000/api/v1/sectors/rank/current"

    def test_env_var(self, monkeypatch) -> None:
        monkeypatch.setenv("FUNDPILOT_URL", "http://prod:9000")
        client = APIClient()
        assert client._base_url == "http://prod:9000"

    def test_get_request(self, respx_mock) -> None:
        respx_mock.get("http://localhost:8000/api/v1/funds").mock(
            return_value=httpx.Response(200, json={"success": True, "data": {}})
        )
        client = APIClient()
        result = client.get("/funds")
        assert result == {"success": True, "data": {}}

    def test_post_request(self, respx_mock) -> None:
        respx_mock.post("http://localhost:8000/api/v1/collect/trigger").mock(
            return_value=httpx.Response(200, json={"success": True, "data": {}})
        )
        client = APIClient()
        result = client.post("/collect/trigger", {"collector": "news"})
        assert result == {"success": True, "data": {}}

    def test_put_request(self, respx_mock) -> None:
        respx_mock.put("http://localhost:8000/api/v1/collect/settings/news").mock(
            return_value=httpx.Response(200, json={"success": True, "data": {}})
        )
        client = APIClient()
        result = client.put("/collect/settings/news", {"interval_seconds": 600})
        assert result == {"success": True, "data": {}}

    def test_http_error_raises(self, respx_mock) -> None:
        respx_mock.get("http://localhost:8000/api/v1/funds/999999").mock(
            return_value=httpx.Response(
                404,
                json={"success": False, "error": {"message": "Not found"}},
            )
        )
        client = APIClient()
        with pytest.raises(httpx.HTTPStatusError):
            client.get("/funds/999999")
