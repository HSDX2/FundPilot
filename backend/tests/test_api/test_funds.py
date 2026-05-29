"""Tests for fund API endpoints."""

import uuid
from datetime import UTC
from unittest.mock import AsyncMock

from httpx import AsyncClient

from app.api.deps import get_fund_estimate_repo, get_fund_nav_repo, get_fund_repo
from app.repositories.fund_repo import FundRepo


def _override_repo(mock_repo):
    """Create an async generator override for dependency injection."""
    async def _override():
        yield mock_repo
    return _override


class TestListFunds:
    async def test_empty_list(self, app, async_client: AsyncClient):
        """GET /api/v1/funds should return empty list when no funds."""
        mock_repo = AsyncMock(spec=FundRepo)
        mock_repo.search.return_value = ([], 0)
        app.dependency_overrides[get_fund_repo] = _override_repo(mock_repo)

        resp = await async_client.get("/api/v1/funds")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["items"] == []
        assert data["data"]["total"] == 0

        app.dependency_overrides.clear()

    async def test_pagination(self, app, async_client: AsyncClient):
        """Pagination parameters should be passed correctly."""
        mock_repo = AsyncMock(spec=FundRepo)
        mock_repo.search.return_value = ([], 0)
        app.dependency_overrides[get_fund_repo] = _override_repo(mock_repo)

        resp = await async_client.get("/api/v1/funds?page=2&page_size=10")
        assert resp.status_code == 200
        mock_repo.search.assert_called_once()
        assert mock_repo.search.call_args.kwargs.get("page") == 2
        assert mock_repo.search.call_args.kwargs.get("page_size") == 10

        app.dependency_overrides.clear()


class TestGetFund:
    async def test_found(self, app, async_client: AsyncClient):
        """GET /api/v1/funds/{code} should return fund when found."""
        from app.models.fund import Fund

        fund = Fund(
            id=uuid.uuid4(),
            code="000001",
            name="Test Fund",
            type="股票型",
            company="Test Co",
        )
        mock_repo = AsyncMock(spec=FundRepo)
        mock_repo.get_by_code.return_value = fund
        app.dependency_overrides[get_fund_repo] = _override_repo(mock_repo)

        resp = await async_client.get("/api/v1/funds/000001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["code"] == "000001"
        assert data["data"]["name"] == "Test Fund"

        app.dependency_overrides.clear()

    async def test_not_found(self, app, async_client: AsyncClient):
        """Non-existent fund should return 404."""
        mock_repo = AsyncMock(spec=FundRepo)
        mock_repo.get_by_code.return_value = None
        app.dependency_overrides[get_fund_repo] = _override_repo(mock_repo)

        resp = await async_client.get("/api/v1/funds/999999")
        assert resp.status_code == 404
        data = resp.json()
        assert data["success"] is False
        assert data["error"]["code"] == "FUND_NOT_FOUND"

        app.dependency_overrides.clear()


class TestGetFundNav:
    async def test_with_date_range(self, app, async_client: AsyncClient):
        """GET /api/v1/funds/{code}/nav should support date filtering."""
        from app.models.fund import Fund

        fund_id = uuid.uuid4()
        fund = Fund(id=fund_id, code="000001", name="Test")

        mock_fund_repo = AsyncMock(spec=FundRepo)
        mock_fund_repo.get_by_code.return_value = fund
        app.dependency_overrides[get_fund_repo] = _override_repo(mock_fund_repo)

        mock_nav_repo = AsyncMock()
        mock_nav_repo.get_by_fund_and_date_range.return_value = []
        app.dependency_overrides[get_fund_nav_repo] = _override_repo(mock_nav_repo)

        resp = await async_client.get(
            "/api/v1/funds/000001/nav"
            "?start_date=2026-01-01&end_date=2026-01-31"
        )
        assert resp.status_code == 200

        mock_nav_repo.get_by_fund_and_date_range.assert_called_once()
        args = mock_nav_repo.get_by_fund_and_date_range.call_args
        assert args[0][1] is not None  # start (positional)
        assert args[0][2] is not None  # end (positional)

        app.dependency_overrides.clear()

    async def test_fund_not_found(self, app, async_client: AsyncClient):
        """Non-existent fund on nav endpoint should return 404."""
        mock_repo = AsyncMock(spec=FundRepo)
        mock_repo.get_by_code.return_value = None
        app.dependency_overrides[get_fund_repo] = _override_repo(mock_repo)

        resp = await async_client.get("/api/v1/funds/999999/nav")
        assert resp.status_code == 404
        data = resp.json()
        assert data["error"]["code"] == "FUND_NOT_FOUND"

        app.dependency_overrides.clear()


class TestGetFundEstimate:
    async def test_found(self, app, async_client: AsyncClient):
        """GET /api/v1/funds/{code}/estimate should return latest estimate."""
        from types import SimpleNamespace

        fund_id = uuid.uuid4()

        class FakeFund:
            id = fund_id
            code = "000001"
            name = "Test"

        estimate = SimpleNamespace(
            id=uuid.uuid4(),
            fund_id=fund_id,
            estimate_nav=1.23,
            estimate_change_pct=-0.15,
        )

        mock_fund_repo = AsyncMock(spec=FundRepo)
        mock_fund_repo.get_by_code.return_value = FakeFund()
        app.dependency_overrides[get_fund_repo] = _override_repo(mock_fund_repo)

        mock_est_repo = AsyncMock()
        mock_est_repo.get_by_fund.return_value = estimate
        app.dependency_overrides[get_fund_estimate_repo] = _override_repo(mock_est_repo)

        resp = await async_client.get("/api/v1/funds/000001/estimate")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["estimate_nav"] == 1.23
        assert data["data"]["estimate_change_pct"] == -0.15

        app.dependency_overrides.clear()

    async def test_not_found(self, app, async_client: AsyncClient):
        """No estimate data should return 200 with null data."""
        class FakeFund:
            id = uuid.uuid4()
            code = "000001"
            name = "Test"

        mock_fund_repo = AsyncMock(spec=FundRepo)
        mock_fund_repo.get_by_code.return_value = FakeFund()
        app.dependency_overrides[get_fund_repo] = _override_repo(mock_fund_repo)

        mock_est_repo = AsyncMock()
        mock_est_repo.get_by_fund.return_value = None
        app.dependency_overrides[get_fund_estimate_repo] = _override_repo(mock_est_repo)

        resp = await async_client.get("/api/v1/funds/000001/estimate")
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"] is None

        app.dependency_overrides.clear()

    async def test_fund_not_found(self, app, async_client: AsyncClient):
        """Non-existent fund on estimate should return 404."""
        mock_repo = AsyncMock(spec=FundRepo)
        mock_repo.get_by_code.return_value = None
        app.dependency_overrides[get_fund_repo] = _override_repo(mock_repo)

        resp = await async_client.get("/api/v1/funds/999999/estimate")
        assert resp.status_code == 404

        app.dependency_overrides.clear()


class TestBatchEstimates:
    async def test_batch_empty(self, app, async_client: AsyncClient):
        """Empty codes should return empty items."""
        mock_fund_repo = AsyncMock(spec=FundRepo)
        mock_fund_repo.get_by_code.return_value = None
        app.dependency_overrides[get_fund_repo] = _override_repo(mock_fund_repo)
        app.dependency_overrides[get_fund_estimate_repo] = _override_repo(AsyncMock())

        resp = await async_client.get("/api/v1/funds/estimates/batch?codes=")
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["items"] == []

        app.dependency_overrides.clear()

    async def test_with_codes(self, app, async_client: AsyncClient):
        """Valid codes should return estimates."""
        from types import SimpleNamespace

        fund_id = uuid.uuid4()

        class FakeFund:
            id = fund_id
            code = "000001"
            name = "Test"

        estimate = SimpleNamespace(
            id=uuid.uuid4(),
            fund_id=fund_id,
            estimate_nav=None,
            estimate_change_pct=0.5,
        )

        mock_fund_repo = AsyncMock(spec=FundRepo)
        mock_fund_repo.get_by_codes.return_value = [FakeFund()]
        app.dependency_overrides[get_fund_repo] = _override_repo(mock_fund_repo)

        mock_est_repo = AsyncMock()
        mock_est_repo.get_by_fund.return_value = estimate
        app.dependency_overrides[get_fund_estimate_repo] = _override_repo(mock_est_repo)

        resp = await async_client.get(
            "/api/v1/funds/estimates/batch?codes=000001,000002"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["data"]["items"]) == 2

        app.dependency_overrides.clear()
