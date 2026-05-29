"""Repository for analysis_reports and fund_advices tables."""

import uuid
from collections.abc import Sequence
from datetime import date

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analysis import AnalysisReport, FundAdvice, Recommendation
from app.models.fund import Fund
from app.models.sector import Sector
from app.repositories.base import BaseRepository


class AnalysisReportRepo(BaseRepository[AnalysisReport]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, AnalysisReport)

    async def get_by_date_and_type(
        self, report_date: date, report_type: str,
    ) -> AnalysisReport | None:
        stmt = (
            select(AnalysisReport)
            .where(
                AnalysisReport.date == report_date,
                AnalysisReport.report_type == report_type,
            )
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_type(
        self,
        report_type: str,
        category: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[AnalysisReport], int]:
        conditions = [AnalysisReport.report_type == report_type]
        if category:
            conditions.append(AnalysisReport.category == category)

        query = select(AnalysisReport).where(and_(*conditions))
        count_q = select(func.count(AnalysisReport.id)).where(and_(*conditions))
        total_result = await self.session.execute(count_q)
        total = total_result.scalar() or 0
        query = query.order_by(AnalysisReport.created_at.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(query)
        return list(result.scalars().all()), total

    async def list_by_type_with_sector(
        self,
        report_type: str,
        category: str | None = None,
        page: int = 1,
        page_size: int = 20,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> tuple[list[tuple[AnalysisReport, str | None]], int]:
        """列表查询，同时返回板块名称."""
        conditions = [AnalysisReport.report_type == report_type]
        if category:
            conditions.append(AnalysisReport.category == category)
        if start_date:
            conditions.append(AnalysisReport.date >= start_date)
        if end_date:
            conditions.append(AnalysisReport.date <= end_date)

        base = (
            select(AnalysisReport, Sector.name)
            .outerjoin(Sector, AnalysisReport.sector_id == Sector.id)
            .where(and_(*conditions))
        )
        count_q = select(func.count(AnalysisReport.id)).where(and_(*conditions))
        total_result = await self.session.execute(count_q)
        total = total_result.scalar() or 0

        query = base.order_by(AnalysisReport.created_at.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(query)
        return result.all(), total

    async def get_latest_by_type(
        self, report_type: str,
    ) -> AnalysisReport | None:
        stmt = (
            select(AnalysisReport)
            .where(AnalysisReport.report_type == report_type)
            .order_by(AnalysisReport.date.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def delete_by_id(self, report_id: uuid.UUID) -> bool:
        report = await self.get(report_id)
        if report is None:
            return False
        await self.session.delete(report)
        await self.session.flush()
        return True

    async def delete_by_ids(self, report_ids: list[uuid.UUID]) -> int:
        """Batch delete reports. Returns count deleted."""
        if not report_ids:
            return 0
        stmt = select(AnalysisReport).where(AnalysisReport.id.in_(report_ids))
        result = await self.session.execute(stmt)
        reports = result.scalars().all()
        for r in reports:
            await self.session.delete(r)
        await self.session.flush()
        return len(reports)


class FundAdviceRepo(BaseRepository[FundAdvice]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, FundAdvice)

    async def get_by_fund_and_date(
        self, fund_id: uuid.UUID, advice_date: date,
    ) -> FundAdvice | None:
        stmt = (
            select(FundAdvice)
            .where(
                FundAdvice.fund_id == fund_id,
                FundAdvice.date == advice_date,
            )
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_fund(
        self,
        fund_id: uuid.UUID,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[FundAdvice], int]:
        query = select(FundAdvice).where(FundAdvice.fund_id == fund_id)
        count_q = select(func.count(FundAdvice.id)).where(
            FundAdvice.fund_id == fund_id
        )
        total_result = await self.session.execute(count_q)
        total = total_result.scalar() or 0
        query = query.order_by(FundAdvice.date.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(query)
        return list(result.scalars().all()), total

    async def list_recent(
        self,
        page: int = 1,
        page_size: int = 20,
        action: str | None = None,
        fund_code: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> tuple[list[tuple[FundAdvice, str | None, str | None]], int]:
        """分页查询建议列表，按 fund_code 筛选，返回 (advice, fund_code, fund_name)."""
        base = (
            select(FundAdvice, Fund.code, Fund.name)
            .outerjoin(Fund, FundAdvice.fund_id == Fund.id)
        )
        count_q = select(func.count(FundAdvice.id)).select_from(FundAdvice)
        conditions = []
        if action:
            conditions.append(FundAdvice.action == action)
        if fund_code:
            conditions.append(Fund.code.ilike(f"%{fund_code}%"))
        if start_date:
            conditions.append(FundAdvice.date >= start_date)
        if end_date:
            conditions.append(FundAdvice.date <= end_date)
        if conditions:
            base = base.where(and_(*conditions))
            count_q = count_q.where(and_(*conditions))

        total_result = await self.session.execute(count_q)
        total = total_result.scalar() or 0

        query = base.order_by(FundAdvice.created_at.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(query)
        return result.all(), total


class RecommendationRepo(BaseRepository[Recommendation]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Recommendation)

    async def list_recent(
        self,
        page: int = 1,
        page_size: int = 20,
        start_date: date | None = None,
        end_date: date | None = None,
        mode: str | None = None,
    ) -> tuple[list[Recommendation], int]:
        conditions = []
        if start_date:
            conditions.append(Recommendation.date >= start_date)
        if end_date:
            conditions.append(Recommendation.date <= end_date)
        if mode:
            conditions.append(Recommendation.mode == mode)

        count_q = select(func.count(Recommendation.id))
        if conditions:
            count_q = count_q.where(and_(*conditions))
        total_result = await self.session.execute(count_q)
        total = total_result.scalar() or 0

        query = select(Recommendation)
        if conditions:
            query = query.where(and_(*conditions))
        query = query.order_by(Recommendation.created_at.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(query)
        return list(result.scalars().all()), total

    async def delete_by_ids(self, ids: list[uuid.UUID]) -> int:
        if not ids:
            return 0
        stmt = select(Recommendation).where(Recommendation.id.in_(ids))
        result = await self.session.execute(stmt)
        items = result.scalars().all()
        for item in items:
            await self.session.delete(item)
        await self.session.flush()
        return len(items)
