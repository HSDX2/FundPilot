-- FundPilot 初始数据
-- collector_settings — 12 个采集器默认配置
-- 匹配 backend/app/core/constants.py 中的 COLLECTOR_META

INSERT INTO public.collector_settings (id, collector_name, display_name, description, interval_seconds, is_active, sort_order, schedule_config, other_config) VALUES
(
    gen_random_uuid(),
    'fund_list',
    '基金列表',
    '采集基金/ETF列表及基本面数据（初始化数据）',
    86400, TRUE, 0,
    '{"mode": "specific_time", "month_days": [1], "specific_time": "00:00:00"}',
    '{}'
),
(
    gen_random_uuid(),
    'fund_nav_history',
    '基金净值历史数据',
    '全量采集所有基金的历史净值和涨跌幅，耗时较长（初始化数据）',
    86400, TRUE, 1,
    '{"mode": "specific_time", "month_days": [1], "specific_time": "01:00:00"}',
    '{"new_only": true, "worker_count": 12}'
),
(
    gen_random_uuid(),
    'fund_nav_daily',
    '基金净值每日数据',
    '每日增量采集所有基金的净值和涨跌幅，耗时较长',
    86400, TRUE, 2,
    '{"mode": "specific_time", "specific_time": "00:00:00"}',
    '{"worker_count": 12}'
),
(
    gen_random_uuid(),
    'fund_estimate',
    '基金实时估值',
    '定时采集全市场基金盘中实时估值',
    86400, TRUE, 3,
    '{"mode": "interval", "weekdays": [1, 2, 3, 4, 5], "active_end_time": "15:30:00", "interval_minutes": 5, "active_start_time": "09:30:00"}',
    '{}'
),
(
    gen_random_uuid(),
    'etf',
    'ETF行情',
    '采集ETF实时行情，更新最新价和涨跌幅',
    86400, TRUE, 4,
    '{"mode": "interval", "weekdays": [1, 2, 3, 4, 5], "active_end_time": "15:00:00", "interval_minutes": 5, "active_start_time": "09:30:00"}',
    '{}'
),
(
    gen_random_uuid(),
    'sector_list',
    '板块列表',
    '采集行业和概念板块列表（初始化数据）',
    86400, TRUE, 10,
    '{"mode": "specific_time", "month_days": [1], "specific_time": "14:00:00"}',
    '{}'
),
(
    gen_random_uuid(),
    'sector_batch_history',
    '板块历史数据',
    '全量采集所有板块历史行情和资金流向（初始化数据）',
    86400, TRUE, 11,
    '{"mode": "specific_time", "month_days": [1], "specific_time": "15:00:00"}',
    '{"sector_new_only": true}'
),
(
    gen_random_uuid(),
    'sector_batch_daily',
    '板块每日数据',
    '每日增量采集所有板块行情和资金流向',
    86400, TRUE, 12,
    '{"mode": "specific_time", "weekdays": [1, 2, 3, 4, 5], "specific_time": "15:30:00"}',
    '{"backfill_mf_detail": true}'
),
(
    gen_random_uuid(),
    'sector_realtime',
    '板块实时行情',
    '定时采集所有板块实时涨跌幅和成交数据',
    86400, TRUE, 13,
    '{"mode": "interval", "weekdays": [1, 2, 3, 4, 5], "active_end_time": "15:30:00", "interval_minutes": 5, "active_start_time": "09:30:00"}',
    '{}'
),
(
    gen_random_uuid(),
    'market_sentiment',
    '市场情绪',
    '采集涨停/跌停/北上资金等情绪指标',
    86400, TRUE, 20,
    '{"mode": "specific_time", "weekdays": [1, 2, 3, 4, 5], "specific_time": "14:00:00"}',
    '{}'
),
(
    gen_random_uuid(),
    'news',
    '新闻',
    '采集金融新闻并关联相关板块',
    86400, TRUE, 21,
    '{"mode": "interval", "active_end_time": "23:00:00", "interval_minutes": 60, "active_start_time": "09:00:00"}',
    '{}'
),
(
    gen_random_uuid(),
    'news_sentiment',
    '新闻情绪分析',
    '定时对未分析新闻执行 AI 情绪评分',
    86400, TRUE, 22,
    '{"mode": "interval", "active_end_time": "23:30:00", "interval_minutes": 60, "active_start_time": "09:30:00"}',
    '{"sentiment_limit": 300, "sentiment_concurrency": 8}'
),
(
    gen_random_uuid(),
    'recommend_top_picks',
    '综合推荐',
    '定时结合市场排行、资金流向、新闻情绪等数据，通过 AI 生成最值得关注的基金和板块推荐',
    86400, TRUE, 23,
    '{"mode": "interval", "active_end_time": "23:00:00", "interval_minutes": 240, "active_start_time": "09:30:00"}',
    '{"recommend_limit": 8}'
),
(
    gen_random_uuid(),
    'recommend_dip_buy',
    '加仓推荐',
    '定时筛选因回调被低估的基金，通过 AI 分析推荐加仓/观望/止损',
    86400, TRUE, 24,
    '{"mode": "interval", "active_end_time": "23:00:00", "interval_minutes": 360, "active_start_time": "09:30:00"}',
    '{"recommend_limit": 8, "max_drawdown": 5.0, "min_consecutive_days": 3}'
)
ON CONFLICT (collector_name) DO NOTHING;
