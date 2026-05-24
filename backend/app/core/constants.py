"""应用常量与枚举定义."""

from enum import StrEnum


class FundType(StrEnum):
    """基金类型编码，用于 API 参数传递。"""

    STOCK = "stock"          # 股票型
    MIXED = "mixed"          # 混合型
    INDEX = "index"          # 指数型
    ETF = "etf"              # ETF
    BOND = "bond"            # 债券型
    MONETARY = "monetary"    # 货币型
    QDII = "qdii"            # QDII


# API 编码 → 数据库中 type 字段的前缀匹配
FUND_TYPE_PREFIX_MAP: dict[FundType, str] = {
    FundType.STOCK: "股票型",
    FundType.MIXED: "混合型",
    FundType.INDEX: "指数型",
    FundType.ETF: "ETF",
    FundType.BOND: "债券型",
    FundType.MONETARY: "货币型",
    FundType.QDII: "QDII",
}

# Phase 1 关注的基金类型
FUND_TYPES_FOCUS = {
    FundType.STOCK, FundType.MIXED, FundType.INDEX, FundType.ETF,
}


class SectorCategory(StrEnum):
    """板块分类编码，用于 API 参数传递。"""

    INDUSTRY = "industry"    # 行业板块
    CONCEPT = "concept"      # 概念板块


class CollectorName(StrEnum):
    """采集器名称编码，对应 collector_settings 表。"""

    FUND_LIST = "fund_list"
    ETF_LIST = "etf_list"
    ETF = "etf"
    SECTOR = "sector"
    SECTOR_LIST = "sector_list"
    SECTOR_DAILY = "sector_daily"
    SECTOR_MONEY_FLOW = "sector_money_flow"
    FUND_ESTIMATE = "fund_estimate"
    FUND_NAV = "fund_nav"
    NEWS = "news"
    MARKET_SENTIMENT = "market_sentiment"


# 默认采集频率 (秒)
DEFAULT_COLLECTOR_INTERVALS: dict[CollectorName, int] = {
    CollectorName.FUND_LIST: 86400,      # 每天
    CollectorName.ETF_LIST: 86400,       # 每天
    CollectorName.ETF: 30,
    CollectorName.SECTOR: 60,
    CollectorName.SECTOR_LIST: 86400,    # 每天
    CollectorName.SECTOR_DAILY: 86400,   # 每天
    CollectorName.FUND_ESTIMATE: 300,
    CollectorName.FUND_NAV: 86400,       # 每天
    CollectorName.SECTOR_MONEY_FLOW: 86400,  # 每天
    CollectorName.NEWS: 600,
    CollectorName.MARKET_SENTIMENT: 86400,  # 每天盘后
}


class AIProviderType(StrEnum):
    """AI 提供商类型。

    All providers except Claude follow OpenAI-compatible API format.
    """

    DEEPSEEK = "deepseek"
    GLM = "glm"
    QWEN = "qwen"
    OPENAI = "openai"
    KIMI = "kimi"
    MINIMAX = "minimax"
    CUSTOM = "custom"
