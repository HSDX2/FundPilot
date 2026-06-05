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
    ETF = "etf"
    SECTOR_LIST = "sector_list"
    FUND_NAV_HISTORY = "fund_nav_history"
    FUND_NAV_DAILY = "fund_nav_daily"
    NEWS = "news"
    MARKET_SENTIMENT = "market_sentiment"
    SECTOR_BATCH_HISTORY = "sector_batch_history"
    SECTOR_BATCH_DAILY = "sector_batch_daily"
    FUND_ESTIMATE = "fund_estimate"
    SECTOR_REALTIME = "sector_realtime"
    NEWS_SENTIMENT = "news_sentiment"
    RECOMMEND_TOP_PICKS = "recommend_top_picks"
    RECOMMEND_DIP_BUY = "recommend_dip_buy"


# 默认采集频率 (秒)
DEFAULT_COLLECTOR_INTERVALS: dict[CollectorName, int] = {
    CollectorName.FUND_LIST: 86400,                  # 每天
    CollectorName.ETF: 30,
    CollectorName.SECTOR_LIST: 86400,                # 每天
    CollectorName.FUND_NAV_HISTORY: 86400,           # 每天
    CollectorName.FUND_NAV_DAILY: 86400,             # 每天
    CollectorName.NEWS: 600,
    CollectorName.MARKET_SENTIMENT: 86400,           # 每天盘后
    CollectorName.SECTOR_BATCH_HISTORY: 86400,       # 每天
    CollectorName.SECTOR_BATCH_DAILY: 86400,         # 每天
    CollectorName.FUND_ESTIMATE: 300,                # 5分钟（交易时段）
    CollectorName.SECTOR_REALTIME: 300,              # 5分钟（交易时段）
    CollectorName.NEWS_SENTIMENT: 3600,              # 每小时
    CollectorName.RECOMMEND_TOP_PICKS: 14400,        # 每4小时
    CollectorName.RECOMMEND_DIP_BUY: 43200,          # 每12小时
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


# 采集器默认元信息：名称、说明、定时策略、额外参数
# 启动时写入 collector_settings 表，已有行会被覆盖
# 数据库实际配置通过 psql 导出同步（不含 AI 配置）
COLLECTOR_META: dict[str, dict] = {
    "fund_list": {
        "display_name": "基金列表",
        "description": "采集基金/ETF列表及基本面数据",
        "sort_order": 0,
        "interval_seconds": 86400,
        "is_active": True,
        "schedule_config": {"mode": "specific_time", "month_days": [1], "specific_time": "00:00:00"},
        "other_config": {},
    },
    "fund_nav_history": {
        "display_name": "基金净值历史数据",
        "description": "覆盖所有基金的历史净值和涨跌幅",
        "sort_order": 1,
        "interval_seconds": 86400,
        "is_active": True,
        "schedule_config": {"mode": "specific_time", "month_days": [1], "specific_time": "01:00:00"},
        "other_config": {"new_only": True, "worker_count": 12},
    },
    "fund_nav_daily": {
        "display_name": "基金净值每日数据",
        "description": "只获取当天的净值和涨跌幅",
        "sort_order": 2,
        "interval_seconds": 86400,
        "is_active": True,
        "schedule_config": {"mode": "specific_time", "specific_time": "15:30:00"},
        "other_config": {"worker_count": 12},
    },
    "fund_estimate": {
        "display_name": "基金实时估值",
        "description": "定时采集全市场基金盘中实时估值",
        "sort_order": 3,
        "interval_seconds": 86400,
        "is_active": True,
        "schedule_config": {"mode": "interval", "weekdays": [1, 2, 3, 4, 5], "active_end_time": "15:30:00", "interval_minutes": 5, "active_start_time": "09:30:00"},
        "other_config": {},
    },
    "etf": {
        "display_name": "ETF行情",
        "description": "采集ETF实时行情，更新最新价和涨跌幅",
        "sort_order": 4,
        "interval_seconds": 86400,
        "is_active": True,
        "schedule_config": {"mode": "interval", "weekdays": [1, 2, 3, 4, 5], "active_end_time": "15:00:00", "interval_minutes": 5, "active_start_time": "09:30:00"},
        "other_config": {},
    },
    "sector_list": {
        "display_name": "板块列表",
        "description": "采集行业和概念板块列表",
        "sort_order": 10,
        "interval_seconds": 86400,
        "is_active": True,
        "schedule_config": {"mode": "specific_time", "month_days": [1], "specific_time": "14:00:00"},
        "other_config": {},
    },
    "sector_batch_history": {
        "display_name": "板块历史数据",
        "description": "全量采集所有板块历史行情和资金流向",
        "sort_order": 11,
        "interval_seconds": 86400,
        "is_active": True,
        "schedule_config": {"mode": "specific_time", "month_days": [1], "specific_time": "15:00:00"},
        "other_config": {"sector_new_only": True},
    },
    "sector_batch_daily": {
        "display_name": "板块每日数据",
        "description": "每日增量采集所有板块行情和资金流向",
        "sort_order": 12,
        "interval_seconds": 86400,
        "is_active": True,
        "schedule_config": {"mode": "specific_time", "weekdays": [1, 2, 3, 4, 5], "specific_time": "15:30:00"},
        "other_config": {"backfill_mf_detail": True},
    },
    "sector_realtime": {
        "display_name": "板块实时行情",
        "description": "定时采集所有板块实时涨跌幅和成交数据",
        "sort_order": 13,
        "interval_seconds": 86400,
        "is_active": True,
        "schedule_config": {"mode": "interval", "weekdays": [1, 2, 3, 4, 5], "active_end_time": "15:30:00", "interval_minutes": 5, "active_start_time": "09:30:00"},
        "other_config": {},
    },
    "market_sentiment": {
        "display_name": "市场情绪",
        "description": "采集涨停/跌停/北上资金等情绪指标",
        "sort_order": 20,
        "interval_seconds": 86400,
        "is_active": True,
        "schedule_config": {"mode": "specific_time", "weekdays": [1, 2, 3, 4, 5], "specific_time": "14:00:00"},
        "other_config": {},
    },
    "news": {
        "display_name": "新闻",
        "description": "采集金融新闻并关联相关板块",
        "sort_order": 21,
        "interval_seconds": 86400,
        "is_active": True,
        "schedule_config": {"mode": "interval", "active_end_time": "23:00:00", "interval_minutes": 60, "active_start_time": "09:00:00"},
        "other_config": {},
    },
    "news_sentiment": {
        "display_name": "新闻情绪分析",
        "description": "定时对未分析新闻执行 AI 情绪评分",
        "sort_order": 22,
        "interval_seconds": 86400,
        "is_active": True,
        "schedule_config": {"mode": "interval", "active_end_time": "23:30:00", "interval_minutes": 60, "active_start_time": "09:30:00"},
        "other_config": {"sentiment_limit": 300, "sentiment_concurrency": 8},
    },
    "recommend_top_picks": {
        "display_name": "综合推荐",
        "description": "定时结合市场排行、资金流向、新闻情绪等数据，通过 AI 生成最值得关注的基金和板块推荐",
        "sort_order": 23,
        "interval_seconds": 86400,
        "is_active": True,
        "schedule_config": {"mode": "interval", "active_end_time": "23:00:00", "interval_minutes": 240, "active_start_time": "09:30:00"},
        "other_config": {"recommend_limit": 8},
    },
    "recommend_dip_buy": {
        "display_name": "加仓推荐",
        "description": "定时筛选因回调被低估的基金，通过 AI 分析推荐加仓/观望/止损",
        "sort_order": 24,
        "interval_seconds": 86400,
        "is_active": True,
        "schedule_config": {"mode": "interval", "active_end_time": "23:00:00", "interval_minutes": 360, "active_start_time": "09:30:00"},
        "other_config": {"recommend_limit": 8, "max_drawdown": 5.0, "min_consecutive_days": 3},
    },
}
