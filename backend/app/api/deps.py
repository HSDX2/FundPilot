"""FastAPI dependency injection."""

from collections.abc import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.repositories.analysis_repo import AnalysisReportRepo, FundAdviceRepo
from app.repositories.fund_repo import (
    FundEstimateRepo,
    FundNavRepo,
    FundRepo,
)
from app.repositories.news_repo import NewsArticleRepo, NewsSectorLinkRepo
from app.repositories.sector_repo import (
    SectorMoneyFlowRepo,
    SectorRepo,
    SectorSnapshotRepo,
)
from app.repositories.sentiment_repo import MarketSentimentRepo
from app.repositories.system_repo import (
    AIProviderRepo,
    CollectLogRepo,
    CollectorSettingRepo,
)
from app.services.analysis_service import AnalysisService
from app.services.collector_service import CollectorService
from app.services.fund_service import FundService
from app.services.sector_service import SectorService


async def get_fund_repo(
    session: AsyncSession = Depends(get_db),
) -> AsyncGenerator[FundRepo]:
    yield FundRepo(session)


async def get_fund_nav_repo(
    session: AsyncSession = Depends(get_db),
) -> AsyncGenerator[FundNavRepo]:
    yield FundNavRepo(session)


async def get_fund_estimate_repo(
    session: AsyncSession = Depends(get_db),
) -> AsyncGenerator[FundEstimateRepo]:
    yield FundEstimateRepo(session)


async def get_sector_repo(
    session: AsyncSession = Depends(get_db),
) -> AsyncGenerator[SectorRepo]:
    yield SectorRepo(session)


async def get_sector_snapshot_repo(
    session: AsyncSession = Depends(get_db),
) -> AsyncGenerator[SectorSnapshotRepo]:
    yield SectorSnapshotRepo(session)


async def get_sector_money_flow_repo(
    session: AsyncSession = Depends(get_db),
) -> AsyncGenerator[SectorMoneyFlowRepo]:
    yield SectorMoneyFlowRepo(session)


async def get_news_article_repo(
    session: AsyncSession = Depends(get_db),
) -> AsyncGenerator[NewsArticleRepo]:
    yield NewsArticleRepo(session)


async def get_collector_setting_repo(
    session: AsyncSession = Depends(get_db),
) -> AsyncGenerator[CollectorSettingRepo]:
    yield CollectorSettingRepo(session)


async def get_collector_service(
    session: AsyncSession = Depends(get_db),
) -> AsyncGenerator[CollectorService]:
    yield CollectorService(
        fund_repo=FundRepo(session),
        fund_nav_repo=FundNavRepo(session),
        fund_estimate_repo=FundEstimateRepo(session),
        sector_repo=SectorRepo(session),
        sector_snapshot_repo=SectorSnapshotRepo(session),
        sector_money_flow_repo=SectorMoneyFlowRepo(session),
        news_repo=NewsArticleRepo(session),
        news_sector_link_repo=NewsSectorLinkRepo(session),
        sentiment_repo=MarketSentimentRepo(session),
        collect_log_repo=CollectLogRepo(session),
    )


async def get_fund_service(
    fund_repo: FundRepo = Depends(get_fund_repo),
    fund_nav_repo: FundNavRepo = Depends(get_fund_nav_repo),
    fund_estimate_repo: FundEstimateRepo = Depends(get_fund_estimate_repo),
) -> AsyncGenerator[FundService]:
    yield FundService(
        fund_repo=fund_repo,
        fund_nav_repo=fund_nav_repo,
        fund_estimate_repo=fund_estimate_repo,
    )


async def get_sector_service(
    sector_repo: SectorRepo = Depends(get_sector_repo),
    sector_snapshot_repo: SectorSnapshotRepo = Depends(get_sector_snapshot_repo),
    sector_money_flow_repo: SectorMoneyFlowRepo = Depends(get_sector_money_flow_repo),
) -> AsyncGenerator[SectorService]:
    yield SectorService(
        sector_repo=sector_repo,
        sector_snapshot_repo=sector_snapshot_repo,
        sector_money_flow_repo=sector_money_flow_repo,
    )


async def get_ai_provider_repo(
    session: AsyncSession = Depends(get_db),
) -> AsyncGenerator[AIProviderRepo]:
    yield AIProviderRepo(session)


async def get_sentiment_repo(
    session: AsyncSession = Depends(get_db),
) -> AsyncGenerator[MarketSentimentRepo]:
    yield MarketSentimentRepo(session)


async def get_analysis_service(
    session: AsyncSession = Depends(get_db),
) -> AsyncGenerator[AnalysisService]:
    yield AnalysisService(
        ai_provider_repo=AIProviderRepo(session),
        analysis_report_repo=AnalysisReportRepo(session),
        fund_advice_repo=FundAdviceRepo(session),
        sector_repo=SectorRepo(session),
        sector_snapshot_repo=SectorSnapshotRepo(session),
        sector_money_flow_repo=SectorMoneyFlowRepo(session),
        fund_repo=FundRepo(session),
        fund_nav_repo=FundNavRepo(session),
        fund_estimate_repo=FundEstimateRepo(session),
        news_repo=NewsArticleRepo(session),
    )
