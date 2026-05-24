"""Tests for constants and enumerations."""

from app.core.constants import (
    DEFAULT_COLLECTOR_INTERVALS,
    FUND_TYPE_PREFIX_MAP,
    FUND_TYPES_FOCUS,
    AIProviderType,
    CollectorName,
    FundType,
    SectorCategory,
)


class TestFundType:
    def test_focus_types(self):
        assert FundType.STOCK in FUND_TYPES_FOCUS
        assert FundType.MIXED in FUND_TYPES_FOCUS
        assert FundType.INDEX in FUND_TYPES_FOCUS
        assert FundType.ETF in FUND_TYPES_FOCUS
        assert FundType.BOND not in FUND_TYPES_FOCUS

    def test_fund_type_values(self):
        """API codes are English, prefix map gives Chinese type prefix."""
        assert FundType.STOCK.value == "stock"
        assert FundType.ETF.value == "etf"

    def test_prefix_map(self):
        assert FUND_TYPE_PREFIX_MAP[FundType.STOCK] == "股票型"
        assert FUND_TYPE_PREFIX_MAP[FundType.ETF] == "ETF"
        assert FUND_TYPE_PREFIX_MAP[FundType.MIXED] == "混合型"
        assert FUND_TYPE_PREFIX_MAP[FundType.INDEX] == "指数型"


class TestSectorCategory:
    def test_values(self):
        assert SectorCategory.INDUSTRY == "industry"
        assert SectorCategory.CONCEPT == "concept"


class TestCollectorName:
    def test_values(self):
        assert CollectorName.FUND_LIST == "fund_list"
        assert CollectorName.ETF_LIST == "etf_list"
        assert CollectorName.ETF == "etf"
        assert CollectorName.SECTOR == "sector"
        assert CollectorName.SECTOR_LIST == "sector_list"
        assert CollectorName.SECTOR_DAILY == "sector_daily"
        assert CollectorName.FUND_ESTIMATE == "fund_estimate"
        assert CollectorName.FUND_NAV == "fund_nav"
        assert CollectorName.NEWS == "news"

    def test_default_intervals(self):
        assert DEFAULT_COLLECTOR_INTERVALS[CollectorName.ETF] == 30
        assert DEFAULT_COLLECTOR_INTERVALS[CollectorName.SECTOR] == 60
        assert DEFAULT_COLLECTOR_INTERVALS[CollectorName.FUND_ESTIMATE] == 300
        assert DEFAULT_COLLECTOR_INTERVALS[CollectorName.NEWS] == 600
        assert DEFAULT_COLLECTOR_INTERVALS[CollectorName.FUND_LIST] == 86400
        assert DEFAULT_COLLECTOR_INTERVALS[CollectorName.ETF_LIST] == 86400
        assert DEFAULT_COLLECTOR_INTERVALS[CollectorName.SECTOR_LIST] == 86400
        assert DEFAULT_COLLECTOR_INTERVALS[CollectorName.SECTOR_DAILY] == 86400
        assert DEFAULT_COLLECTOR_INTERVALS[CollectorName.FUND_NAV] == 86400


class TestAIProviderType:
    def test_values(self):
        assert AIProviderType.DEEPSEEK == "deepseek"
        assert AIProviderType.GLM == "glm"
        assert AIProviderType.QWEN == "qwen"
        assert AIProviderType.OPENAI == "openai"
        assert AIProviderType.KIMI == "kimi"
        assert AIProviderType.MINIMAX == "minimax"
        assert AIProviderType.CUSTOM == "custom"
