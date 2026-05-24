"""Tests for unified API response format."""

import json

from app.core.errors import ErrorCode
from app.core.response import ApiResponse


class TestApiResponse:
    def _body(self, resp):
        return json.loads(resp.body)

    def test_success_response(self):
        """Success response should have correct format."""
        resp = ApiResponse.success(data={"key": "value"}, message="ok")
        body = self._body(resp)
        assert resp.status_code == 200
        assert body["success"] is True
        assert body["data"] == {"key": "value"}
        assert body["message"] == "ok"

    def test_success_without_data(self):
        """Success with no data should return None."""
        resp = ApiResponse.success()
        body = self._body(resp)
        assert body["success"] is True
        assert body["data"] is None

    def test_success_custom_status(self):
        """Success response should accept custom status code."""
        resp = ApiResponse.success(data=None, status_code=201)
        assert resp.status_code == 201

    def test_error_response_format(self):
        """Error response should have correct structure."""
        resp = ApiResponse.error(
            ErrorCode.FUND_NOT_FOUND,
            "Fund not found",
            status_code=404,
        )
        body = self._body(resp)
        assert resp.status_code == 404
        assert body["success"] is False
        assert body["error"]["code"] == "FUND_NOT_FOUND"
        assert body["error"]["message"] == "Fund not found"

    def test_error_default_status(self):
        """Error should use default status when not specified."""
        resp = ApiResponse.error(ErrorCode.INVALID_ARGUMENT, "bad request")
        assert resp.status_code == 400
