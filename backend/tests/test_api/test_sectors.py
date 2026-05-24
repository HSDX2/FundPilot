"""Tests for sector API endpoints."""

import uuid
from datetime import UTC
from unittest.mock import AsyncMock

from httpx import AsyncClient

from app.api.deps import (
    get_sector_repo,
    get_sector_snapshot_repo,
)
from app.repositories.sector_repo import SectorRepo


def _override(mock_repo):
    async def _fn():
        yield mock_repo
    return _fn


class TestListSectors:
    async def test_empty_list(self, app, async_client: AsyncClient):
        """GET /api/v1/sectors should return empty list."""
        mock_repo = AsyncMock(spec=SectorRepo)
        mock_repo.search.return_value = ([], 0)
        app.dependency_overrides[get_sector_repo] = _override(mock_repo)

        resp = await async_client.get("/api/v1/sectors")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["items"] == []

        app.dependency_overrides.clear()

    async def test_filter_by_category(self, app, async_client: AsyncClient):
        """Category filter should be passed to repo."""
        mock_repo = AsyncMock(spec=SectorRepo)
        mock_repo.search.return_value = ([], 0)
        app.dependency_overrides[get_sector_repo] = _override(mock_repo)

        await async_client.get("/api/v1/sectors?category=industry")
        assert mock_repo.search.call_args.kwargs.get("category") == "industry"

        app.dependency_overrides.clear()


class TestGetSector:
    async def test_found(self, app, async_client: AsyncClient):
        """Existing sector should return 200 with data."""
        from types import SimpleNamespace

        sid = uuid.uuid4()
        sector = SimpleNamespace(
            id=sid,
            name="半导体",
            code="BK0891",
            category="industry",
            description="半导体板块",
        )

        mock_repo = AsyncMock(spec=SectorRepo)
        mock_repo.get.return_value = sector
        app.dependency_overrides[get_sector_repo] = _override(mock_repo)

        resp = await async_client.get(f"/api/v1/sectors/{sid}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["name"] == "半导体"

        app.dependency_overrides.clear()

    async def test_not_found(self, app, async_client: AsyncClient):
        """Non-existent sector ID should return 404."""
        mock_repo = AsyncMock(spec=SectorRepo)
        mock_repo.get.return_value = None
        app.dependency_overrides[get_sector_repo] = _override(mock_repo)

        resp = await async_client.get(f"/api/v1/sectors/{uuid.uuid4()}")
        assert resp.status_code == 404

        app.dependency_overrides.clear()

    async def test_invalid_id_format(self, app, async_client: AsyncClient):
        """Invalid UUID should return 400."""
        resp = await async_client.get("/api/v1/sectors/not-a-uuid")
        assert resp.status_code == 400
        data = resp.json()
        assert data["error"]["code"] == "INVALID_ARGUMENT"


class TestGetSectorSnapshots:
    async def test_basic(self, app, async_client: AsyncClient):
        """Snapshots endpoint should return data with date range."""
        from types import SimpleNamespace

        sid = uuid.uuid4()
        mock_sector = SimpleNamespace(id=sid)

        mock_sector_repo = AsyncMock(spec=SectorRepo)
        mock_sector_repo.get.return_value = mock_sector
        app.dependency_overrides[get_sector_repo] = _override(mock_sector_repo)

        mock_snapshot_repo = AsyncMock()
        mock_snapshot_repo.get_by_sector_and_time_range.return_value = []
        app.dependency_overrides[get_sector_snapshot_repo] = _override(
            mock_snapshot_repo
        )

        resp = await async_client.get(
            f"/api/v1/sectors/{sid}/snapshots"
            "?start_time=2026-05-23T09:30:00&end_time=2026-05-23T15:00:00"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True

        app.dependency_overrides.clear()

    async def test_sector_not_found(self, app, async_client: AsyncClient):
        """Non-existent sector on snapshots should return 404."""
        sid = uuid.uuid4()
        mock_repo = AsyncMock(spec=SectorRepo)
        mock_repo.get.return_value = None
        app.dependency_overrides[get_sector_repo] = _override(mock_repo)

        resp = await async_client.get(f"/api/v1/sectors/{sid}/snapshots")
        assert resp.status_code == 404

        app.dependency_overrides.clear()


class TestGetSectorRealtime:
    async def test_found(self, app, async_client: AsyncClient):
        """Realtime endpoint should return latest snapshot."""
        from datetime import datetime
        from types import SimpleNamespace

        sid = uuid.uuid4()

        class FakeSector:
            id = sid

        mock_sector_repo = AsyncMock(spec=SectorRepo)
        mock_sector_repo.get.return_value = FakeSector()
        app.dependency_overrides[get_sector_repo] = _override(mock_sector_repo)

        snapshot = SimpleNamespace(
            id=uuid.uuid4(),
            sector_id=sid,
            timestamp=datetime(2026, 5, 23, 14, 0, tzinfo=UTC),
            price=None,
            open=None,
            high=None,
            low=None,
            change_pct=2.5,
            volume=None,
            turnover=None,
        )

        mock_snapshot_repo = AsyncMock()
        mock_snapshot_repo.get_latest_by_sector.return_value = snapshot
        app.dependency_overrides[get_sector_snapshot_repo] = _override(
            mock_snapshot_repo
        )

        resp = await async_client.get(f"/api/v1/sectors/{sid}/realtime")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True

        app.dependency_overrides.clear()

    async def test_not_found(self, app, async_client: AsyncClient):
        """No snapshot data should return 200 with null data."""
        from types import SimpleNamespace

        sid = uuid.uuid4()
        mock_sector = SimpleNamespace(id=sid)

        mock_sector_repo = AsyncMock(spec=SectorRepo)
        mock_sector_repo.get.return_value = mock_sector
        app.dependency_overrides[get_sector_repo] = _override(mock_sector_repo)

        mock_snapshot_repo = AsyncMock()
        mock_snapshot_repo.get_latest_by_sector.return_value = None
        app.dependency_overrides[get_sector_snapshot_repo] = _override(
            mock_snapshot_repo
        )

        resp = await async_client.get(f"/api/v1/sectors/{sid}/realtime")
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"] is None

        app.dependency_overrides.clear()


class TestSectorRank:
    async def test_empty_rank(self, app, async_client: AsyncClient):
        """Rank endpoint should handle no data."""
        from app.api.deps import get_db

        def _override_db():
            session = AsyncMock()
            session.execute.return_value.scalar.return_value = None
            async def _fn():
                yield session
            return _fn

        app.dependency_overrides[get_db] = _override_db()
        app.dependency_overrides[get_sector_snapshot_repo] = _override(
            AsyncMock()
        )

        resp = await async_client.get("/api/v1/sectors/rank/current")
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["items"] == []

        app.dependency_overrides.clear()

    async def test_with_data(self, app, async_client: AsyncClient):
        """Rank endpoint should return ranked data when snapshots exist."""
        from datetime import datetime
        from types import SimpleNamespace

        from app.api.deps import get_db

        sid = uuid.uuid4()

        def _override_db():
            session = AsyncMock()
            session.execute.return_value.scalar.return_value = (
                datetime(2026, 5, 23, 14, 0, tzinfo=UTC)
            )
            async def _fn():
                yield session
            return _fn

        snapshot = SimpleNamespace(
            price=3500.5,
            change_pct=5.2,
            timestamp=datetime(2026, 5, 23, 14, 0, tzinfo=UTC),
            volume=1000000,
            turnover=500000.0,
        )
        sector = SimpleNamespace(
            id=sid,
            name="半导体",
            category="industry",
        )

        mock_snapshot_repo = AsyncMock()
        mock_snapshot_repo.get_rank_by_timestamp.return_value = [
            (snapshot, sector)
        ]

        app.dependency_overrides[get_db] = _override_db()
        app.dependency_overrides[get_sector_snapshot_repo] = _override(
            mock_snapshot_repo
        )

        resp = await async_client.get("/api/v1/sectors/rank/current")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["data"]["items"]) == 1
        assert data["data"]["items"][0]["sector_name"] == "半导体"

        app.dependency_overrides.clear()
