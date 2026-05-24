"""Tests for fund Pydantic schemas."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from app.schemas.fund import (
    FundEstimateListData,
    FundEstimateResponse,
    FundListData,
    FundNavListData,
    FundNavResponse,
    FundResponse,
)


def _make_uuid() -> UUID:
    return uuid4()


class TestFundResponse:
    def test_from_attributes(self):
        data = FundResponse(
            id=_make_uuid(),
            code="000001",
            name="Test Fund",
            type="股票型",
            company="Test Co",
            established_date=date(2020, 1, 1),
            scale=Decimal("1.5"),
            fund_manager="John",
        )
        assert data.code == "000001"
        assert data.type == "股票型"
        assert data.established_date == date(2020, 1, 1)

    def test_optional_fields_default_to_none(self):
        data = FundResponse(id=_make_uuid(), code="000001", name="Minimal")
        assert data.type is None
        assert data.company is None
        assert data.scale is None


class TestFundNavResponse:
    def test_basic(self):
        uid = _make_uuid()
        data = FundNavResponse(
            id=uid,
            fund_id=_make_uuid(),
            date=date(2026, 1, 5),
            nav=Decimal("1.2345"),
            accumulated_nav=Decimal("2.3456"),
            daily_change_pct=Decimal("0.12"),
        )
        assert data.nav == Decimal("1.2345")
        assert data.daily_change_pct == Decimal("0.12")


class TestFundEstimateResponse:
    def test_basic(self):
        data = FundEstimateResponse(
            id=_make_uuid(),
            fund_id=_make_uuid(),
            timestamp=datetime(2026, 5, 23, 10, 30),
            estimate_nav=Decimal("1.2345"),
            estimate_change_pct=Decimal("-0.15"),
            estimate_change_amount=Decimal("-0.0018"),
        )
        assert data.estimate_change_pct == Decimal("-0.15")


class TestListData:
    def test_fund_list_data(self):
        items = [FundResponse(id=_make_uuid(), code="000001", name="A")]
        data = FundListData(items=items, total=1, page=1, page_size=20)
        assert data.total == 1
        assert len(data.items) == 1

    def test_nav_list_data(self):
        nav = FundNavResponse(
            id=_make_uuid(), fund_id=_make_uuid(), date=date.today()
        )
        items = [nav]
        data = FundNavListData(items=items)
        assert len(data.items) == 1

    def test_estimate_list_data(self):
        items = [FundEstimateResponse(id=_make_uuid(), fund_id=_make_uuid(),
                                       timestamp=datetime(2026, 5, 23, 10, 30))]
        data = FundEstimateListData(items=items)
        assert len(data.items) == 1
