"""Tests for error handling."""


from app.core.errors import (
    AppError,
    CollectorBusyError,
    CollectorNotFoundError,
    DataSourceError,
    ErrorCode,
    FundNotFoundError,
    InvalidArgumentError,
    SectorNotFoundError,
    error_response,
)


class TestErrorCode:
    def test_error_codes_are_unique(self):
        codes = [
            ErrorCode.INTERNAL_ERROR,
            ErrorCode.INVALID_ARGUMENT,
            ErrorCode.FUND_NOT_FOUND,
            ErrorCode.SECTOR_NOT_FOUND,
            ErrorCode.COLLECTOR_NOT_FOUND,
            ErrorCode.COLLECTOR_BUSY,
            ErrorCode.DATA_SOURCE_ERROR,
        ]
        assert len(codes) == len(set(codes))


class TestAppError:
    def test_base_exception(self):
        exc = AppError(
            code=ErrorCode.INVALID_ARGUMENT,
            message="test error",
            status_code=400,
        )
        assert exc.code == "INVALID_ARGUMENT"
        assert exc.message == "test error"
        assert exc.status_code == 400
        assert str(exc) == "test error"

    def test_default_status_code(self):
        exc = AppError(code=ErrorCode.INTERNAL_ERROR)
        assert exc.status_code == 500

    def test_unknown_code_defaults_to_500(self):
        exc = AppError(code="UNKNOWN")
        assert exc.status_code == 500


class TestConcreteExceptions:
    def test_fund_not_found(self):
        exc = FundNotFoundError("000000")
        assert exc.code == "FUND_NOT_FOUND"
        assert "000000" in exc.message
        assert exc.status_code == 404

    def test_sector_not_found(self):
        exc = SectorNotFoundError("uuid-123")
        assert exc.code == "SECTOR_NOT_FOUND"
        assert exc.status_code == 404

    def test_collector_not_found(self):
        exc = CollectorNotFoundError("etf")
        assert exc.code == "COLLECTOR_NOT_FOUND"
        assert "etf" in exc.message
        assert exc.status_code == 404

    def test_collector_busy(self):
        exc = CollectorBusyError("etf")
        assert exc.code == "COLLECTOR_BUSY"
        assert exc.status_code == 409

    def test_invalid_argument(self):
        exc = InvalidArgumentError("bad param")
        assert exc.code == "INVALID_ARGUMENT"
        assert exc.status_code == 400

    def test_data_source_error(self):
        exc = DataSourceError("akshare", "connection timeout")
        assert exc.code == "DATA_SOURCE_ERROR"
        assert exc.status_code == 502


class TestErrorResponse:
    def test_error_response_format(self):
        resp = error_response("TEST_CODE", "test message")
        assert resp["success"] is False
        assert resp["error"]["code"] == "TEST_CODE"
        assert resp["error"]["message"] == "test message"
        assert "data" not in resp["error"]

    def test_error_response_with_data(self):
        resp = error_response("CODE", "msg", data={"extra": "info"})
        assert resp["error"]["data"] == {"extra": "info"}
