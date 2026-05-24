"""Fund business logic — data transformation and orchestration."""

from datetime import date

from app.core.constants import FUND_TYPE_PREFIX_MAP
from app.repositories.fund_repo import FundEstimateRepo, FundNavRepo, FundRepo
from app.schemas.fund import (
    FundEstimateListData,
    FundEstimateResponse,
    FundListData,
    FundNavListData,
    FundNavResponse,
    FundResponse,
)


class FundService:
    """Fund-related business logic."""

    def __init__(
        self,
        fund_repo: FundRepo,
        fund_nav_repo: FundNavRepo | None = None,
        fund_estimate_repo: FundEstimateRepo | None = None,
    ):
        self._fund_repo = fund_repo
        self._nav_repo = fund_nav_repo
        self._est_repo = fund_estimate_repo

    async def search_funds(
        self,
        name: str | None = None,
        type_: str | None = None,
        company: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> FundListData:
        db_type = None
        if type_:
            db_type = FUND_TYPE_PREFIX_MAP.get(type_)

        items, total = await self._fund_repo.search(
            name=name,
            type_=db_type,
            company=company,
            page=page,
            page_size=page_size,
        )
        return FundListData(
            items=[FundResponse.model_validate(f) for f in items],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def get_fund_by_code(self, code: str) -> FundResponse | None:
        fund = await self._fund_repo.get_by_code(code)
        if fund is None:
            return None
        return FundResponse.model_validate(fund)

    async def get_fund_nav_history(
        self,
        fund_id,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> FundNavListData:
        if self._nav_repo is None:
            return FundNavListData(items=[])
        navs = await self._nav_repo.get_by_fund_and_date_range(
            fund_id, start_date, end_date,
        )
        return FundNavListData(
            items=[FundNavResponse.model_validate(n) for n in navs],
        )

    async def get_fund_estimate(
        self,
        fund_id,
    ) -> FundEstimateResponse | None:
        if self._est_repo is None:
            return None
        estimate = await self._est_repo.get_latest_by_fund(fund_id)
        if estimate is None:
            return None
        return FundEstimateResponse.model_validate(estimate)

    async def get_batch_estimates(
        self,
        codes: list[str],
    ) -> FundEstimateListData:
        if self._est_repo is None:
            return FundEstimateListData(items=[])
        items = []
        for code in codes:
            fund = await self._fund_repo.get_by_code(code)
            if fund is None:
                continue
            estimate = await self._est_repo.get_latest_by_fund(fund.id)
            if estimate:
                items.append(
                    FundEstimateResponse.model_validate(estimate).model_dump()
                )
        return FundEstimateListData(items=items)
