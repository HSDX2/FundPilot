"""Repository for analysis_reports and fund_advices tables."""

import uuid
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analysis import AnalysisReport, FundAdvice
from app.repositories.base import BaseRepository


class AnalysisReportRepo(BaseRepository[AnalysisReport]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(AnalysisReport, session)

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
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[AnalysisReport], int]:
        query = select(AnalysisReport).where(
            AnalysisReport.report_type == report_type
        )
        count_q = select(func.count(AnalysisReport.id)).where(
            AnalysisReport.report_type == report_type
        )
        total_result = await self.session.execute(count_q)
        total = total_result.scalar() or 0
        query = query.order_by(AnalysisReport.date.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(query)
        return list(result.scalars().all()), total

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


class FundAdviceRepo(BaseRepository[FundAdvice]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(FundAdvice, session)

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
    ) -> tuple[list[FundAdvice], int]:
        query = select(FundAdvice)
        count_q = select(func.count(FundAdvice.id))
        if action:
            query = query.where(FundAdvice.action == action)
            count_q = count_q.where(FundAdvice.action == action)
        total_result = await self.session.execute(count_q)
        total = total_result.scalar() or 0
        query = query.order_by(FundAdvice.date.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(query)
        return list(result.scalars().all()), total
