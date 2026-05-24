"""SQLAlchemy ORM models.

Import all models so Base.metadata is fully registered.
"""

from app.models.analysis import AnalysisReport, FundAdvice
from app.models.base import Base, TimestampMixin
from app.models.fund import Fund, FundEstimate, FundNav
from app.models.news import NewsArticle, NewsSectorLink
from app.models.sector import Sector, SectorMoneyFlow, SectorSnapshot
from app.models.sentiment import MarketSentiment
from app.models.system import AIProvider, CollectorSetting

__all__ = [
    "Base",
    "TimestampMixin",
    "Fund",
    "FundNav",
    "FundEstimate",
    "Sector",
    "SectorSnapshot",
    "SectorMoneyFlow",
    "MarketSentiment",
    "NewsArticle",
    "NewsSectorLink",
    "AnalysisReport",
    "FundAdvice",
    "AIProvider",
    "CollectorSetting",
]
