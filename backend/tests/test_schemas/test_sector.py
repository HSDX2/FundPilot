"""Tests for sector Pydantic schemas."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from app.schemas.sector import (
    SectorListData,
    SectorRankItem,
    SectorRankListData,
    SectorResponse,
    SectorSnapshotListData,
    SectorSnapshotResponse,
)


def _uid() -> UUID:
    return uuid4()


class TestSectorResponse:
    def test_basic(self):
        data = SectorResponse(
            id=_uid(),
            name="半导体",
            code="BK0891",
            category="industry",
        )
        assert data.name == "半导体"
        assert data.category == "industry"

    def test_optional_fields(self):
        data = SectorResponse(id=_uid(), name="Test", category="concept")
        assert data.code is None
        assert data.description is None


class TestSectorSnapshotResponse:
    def test_basic(self):
        data = SectorSnapshotResponse(
            id=_uid(),
            sector_id=_uid(),
            timestamp=datetime(2026, 5, 23, 14, 0),
            price=Decimal("3500.5"),
            change_pct=Decimal("2.15"),
        )
        assert data.price == Decimal("3500.5")

    def test_list_data(self):
        items = [
            SectorSnapshotResponse(
                id=_uid(), sector_id=_uid(),
                timestamp=datetime(2026, 5, 23, 14, 0),
            )
        ]
        data = SectorSnapshotListData(items=items)
        assert len(data.items) == 1


class TestSectorRank:
    def test_rank_item(self):
        item = SectorRankItem(
            sector_id=_uid(),
            sector_name="半导体",
            category="industry",
            change_pct=Decimal("5.2"),
            price=Decimal("3500.0"),
        )
        assert item.change_pct == Decimal("5.2")

    def test_rank_list_data(self):
        items = [
            SectorRankItem(
                sector_id=_uid(), sector_name="A", category="industry",
                change_pct=Decimal("3.0"),
            ),
            SectorRankItem(
                sector_id=_uid(), sector_name="B", category="concept",
                change_pct=Decimal("1.5"),
            ),
        ]
        data = SectorRankListData(items=items)
        assert len(data.items) == 2


class TestSectorListData:
    def test_basic(self):
        items = [SectorResponse(id=_uid(), name="A", category="industry")]
        data = SectorListData(items=items, total=1, page=1, page_size=20)
        assert data.total == 1
