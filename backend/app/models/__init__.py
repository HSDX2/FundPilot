"""SQLAlchemy ORM models.

Import all models so Base.metadata is fully registered.
"""

from app.models.analysis import AnalysisReport, FundAdvice, Recommendation
from app.models.base import Base, TimestampMixin
from app.models.fund import Fund, FundEstimate, FundNav
from app.models.news import NewsArticle, NewsSectorLink
from app.models.sector import Sector, SectorMoneyFlow, SectorRealtime, SectorSnapshot
from app.models.sentiment import MarketSentiment
from app.models.system import AIProvider, CollectLog, CollectorSetting, PromptSetting
from app.models.watchlist import WatchedFund, WatchedSector

__all__ = [
    "Base",
    "TimestampMixin",
    "Fund",
    "FundNav",
    "FundEstimate",
    "Sector",
    "SectorSnapshot",
    "SectorMoneyFlow",
    "SectorRealtime",
    "MarketSentiment",
    "NewsArticle",
    "NewsSectorLink",
    "AnalysisReport",
    "FundAdvice",
    "Recommendation",
    "AIProvider",
    "CollectorSetting",
    "CollectLog",
    "PromptSetting",
    "WatchedFund",
    "WatchedSector",
]
