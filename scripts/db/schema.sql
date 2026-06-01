-- FundPilot 数据库表结构
-- 从 SQLAlchemy models 导出，移除了 Python 层建表逻辑
-- PostgreSQL 16 适用

-- ── 基金 ─────────────────────────────────────────────────────

CREATE TABLE public.funds (
    id              uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    code            character varying(16) NOT NULL,
    name            character varying(255) NOT NULL,
    type            character varying(32),
    company         character varying(128),
    established_date date,
    scale           numeric(20,4),
    fund_manager    character varying(64),
    latest_price    numeric(12,4),
    latest_change_pct numeric(8,4),
    created_at      timestamp with time zone DEFAULT now() NOT NULL,
    updated_at      timestamp with time zone DEFAULT now() NOT NULL
);
CREATE UNIQUE INDEX ix_funds_code ON public.funds USING btree (code);

CREATE TABLE public.fund_navs (
    id              uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    fund_id         uuid NOT NULL REFERENCES public.funds(id),
    date            date NOT NULL,
    nav             numeric(12,4),
    accumulated_nav numeric(12,4),
    daily_change_pct numeric(8,4),
    created_at      timestamp with time zone DEFAULT now() NOT NULL,
    updated_at      timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT uq_fund_nav_date UNIQUE (fund_id, date)
);

CREATE TABLE public.fund_estimates (
    id              uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    fund_id         uuid NOT NULL REFERENCES public.funds(id),
    estimate_nav    numeric(12,4),
    estimate_change_pct numeric(8,4),
    created_at      timestamp with time zone DEFAULT now() NOT NULL,
    updated_at      timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT uq_fund_estimate_fund UNIQUE (fund_id)
);

-- ── 板块 ─────────────────────────────────────────────────────

CREATE TABLE public.sectors (
    id              uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    name            character varying(64) NOT NULL,
    code            character varying(32),
    category        character varying(16) NOT NULL,
    description     character varying,
    created_at      timestamp with time zone DEFAULT now() NOT NULL,
    updated_at      timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT sectors_code_key UNIQUE (code)
);
CREATE INDEX ix_sectors_category ON public.sectors USING btree (category);

CREATE TABLE public.sector_snapshots (
    id              uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    sector_id       uuid NOT NULL REFERENCES public.sectors(id),
    "timestamp"     date NOT NULL,
    price           numeric(14,4),
    open            numeric(14,4),
    high            numeric(14,4),
    low             numeric(14,4),
    change_pct      numeric(8,4),
    volume          numeric(20,0),
    turnover        numeric(20,4),
    created_at      timestamp with time zone DEFAULT now() NOT NULL,
    updated_at      timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT uq_sector_snapshot_ts UNIQUE (sector_id, "timestamp")
);

CREATE TABLE public.sector_money_flows (
    id              uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    sector_id       uuid NOT NULL REFERENCES public.sectors(id),
    date            date NOT NULL,
    main_force_net_inflow numeric(20,4),
    retail_net_inflow numeric(20,4),
    middle_net_inflow numeric(20,4),
    created_at      timestamp with time zone DEFAULT now() NOT NULL,
    updated_at      timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT uq_sector_money_flow_date UNIQUE (sector_id, date)
);

CREATE TABLE public.sector_realtime (
    id              uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    sector_id       uuid NOT NULL REFERENCES public.sectors(id),
    price           numeric(14,4),
    change_pct      numeric(8,4),
    volume          numeric(20,0),
    turnover        numeric(20,4),
    created_at      timestamp with time zone DEFAULT now() NOT NULL,
    updated_at      timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT sector_realtime_sector_id_key UNIQUE (sector_id)
);

-- ── 新闻 ─────────────────────────────────────────────────────

CREATE TABLE public.news_articles (
    id              uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    title           text NOT NULL,
    content         text,
    source          character varying(32),
    url             text,
    published_at    timestamp with time zone,
    sentiment_score numeric(4,2),
    sentiment_detail json,
    created_at      timestamp with time zone DEFAULT now() NOT NULL,
    updated_at      timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT news_articles_url_key UNIQUE (url)
);

CREATE TABLE public.news_sector_links (
    news_id         uuid NOT NULL REFERENCES public.news_articles(id),
    sector_id       uuid NOT NULL REFERENCES public.sectors(id),
    relevance_score numeric(4,2),
    PRIMARY KEY (news_id, sector_id)
);

-- ── AI 分析 ──────────────────────────────────────────────────

CREATE TABLE public.analysis_reports (
    id              uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    date            date NOT NULL,
    report_type     character varying(16) NOT NULL,
    content         jsonb NOT NULL,
    ai_model        character varying(64),
    category        character varying(16),
    sector_id       uuid,
    sentiment_detail json,
    created_at      timestamp with time zone DEFAULT now() NOT NULL,
    updated_at      timestamp with time zone DEFAULT now() NOT NULL
);
CREATE INDEX ix_analysis_reports_date ON public.analysis_reports USING btree (date);

CREATE TABLE public.fund_advices (
    id              uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    fund_id         uuid NOT NULL REFERENCES public.funds(id),
    date            date NOT NULL,
    action          character varying(16) NOT NULL,
    reason          jsonb NOT NULL,
    confidence      numeric(4,2),
    ai_model        character varying(64),
    created_at      timestamp with time zone DEFAULT now() NOT NULL,
    updated_at      timestamp with time zone DEFAULT now() NOT NULL
);

-- ── 市场情绪 ─────────────────────────────────────────────────

CREATE TABLE public.market_sentiments (
    id              uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    date            date NOT NULL,
    limit_up_count  numeric(6,0),
    limit_down_count numeric(6,0),
    limit_up_broken_count numeric(6,0),
    consecutive_limit_up_count numeric(6,0),
    north_bound_net_inflow numeric(20,4),
    margin_balance_sse numeric(20,4),
    margin_balance_szse numeric(20,4),
    lhb_stock_count numeric(6,0),
    advance_count   numeric(6,0),
    decline_count   numeric(6,0),
    market_total_cap numeric(20,4),
    composite_sentiment_score numeric(6,2),
    extra           jsonb,
    created_at      timestamp with time zone DEFAULT now() NOT NULL,
    updated_at      timestamp with time zone DEFAULT now() NOT NULL
);
CREATE UNIQUE INDEX ix_market_sentiments_date ON public.market_sentiments USING btree (date);

-- ── 自选关注 ─────────────────────────────────────────────────

CREATE TABLE public.watched_funds (
    id              uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    fund_id         uuid NOT NULL REFERENCES public.funds(id),
    added_at        timestamp with time zone DEFAULT now() NOT NULL,
    holding_shares  numeric(16,2),
    CONSTRAINT watched_funds_fund_id_key UNIQUE (fund_id)
);

CREATE TABLE public.watched_sectors (
    id              uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    sector_id       uuid NOT NULL REFERENCES public.sectors(id),
    added_at        timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT watched_sectors_sector_id_key UNIQUE (sector_id)
);

-- ── 采集器 ───────────────────────────────────────────────────

CREATE TABLE public.collector_settings (
    id              uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    collector_name  character varying(32) NOT NULL,
    display_name    character varying(64),
    description     character varying(256),
    interval_seconds integer NOT NULL,
    is_active       boolean NOT NULL,
    sort_order      integer DEFAULT 0 NOT NULL,
    schedule_config jsonb,
    other_config    jsonb,
    last_run_at     timestamp with time zone,
    last_status     character varying(16),
    created_at      timestamp with time zone DEFAULT now() NOT NULL,
    updated_at      timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT collector_settings_collector_name_key UNIQUE (collector_name)
);

CREATE TABLE public.collect_logs (
    id              uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    collector_name  character varying(32) NOT NULL,
    status          character varying(16) NOT NULL,
    records_added   integer NOT NULL,
    records_updated integer NOT NULL,
    error_message   text,
    duration_ms     bigint,
    started_at      timestamp with time zone,
    finished_at     timestamp with time zone,
    created_at      timestamp with time zone DEFAULT now() NOT NULL,
    updated_at      timestamp with time zone DEFAULT now() NOT NULL
);
CREATE INDEX ix_collect_logs_collector_name ON public.collect_logs USING btree (collector_name);

-- ── AI 配置 ──────────────────────────────────────────────────

CREATE TABLE public.ai_providers (
    id              uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    name            character varying(64) NOT NULL,
    provider_type   character varying(32) NOT NULL,
    api_key         text,
    api_base_url    text,
    model_name      character varying(64),
    is_active       boolean NOT NULL,
    web_search_enabled boolean DEFAULT FALSE,
    reasoning_enabled  boolean DEFAULT FALSE,
    extra_config    jsonb,
    created_at      timestamp with time zone DEFAULT now() NOT NULL,
    updated_at      timestamp with time zone DEFAULT now() NOT NULL
);

-- ── 推荐结果 ────────────────────────────────────────────────

CREATE TABLE public.recommendations (
    id              uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    date            date NOT NULL,
    mode            character varying(16),
    rec_type        character varying(16) NOT NULL,
    action          character varying(16) NOT NULL,
    target_name     character varying(128) NOT NULL,
    target_code     character varying(64),
    confidence      numeric(3),
    reason_summary  character varying(1024) DEFAULT '' NOT NULL,
    risk_warning    character varying(512),
    reason_detail   jsonb,
    source_data     jsonb,
    created_at      timestamp with time zone DEFAULT now() NOT NULL,
    updated_at      timestamp with time zone DEFAULT now() NOT NULL
);
CREATE INDEX ix_recommendations_date ON public.recommendations USING btree (date);

CREATE TABLE public.prompt_settings (
    id              uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    prompt_key      character varying(64) NOT NULL,
    prompt_text     text NOT NULL,
    created_at      timestamp with time zone DEFAULT now() NOT NULL,
    updated_at      timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT prompt_settings_prompt_key_key UNIQUE (prompt_key)
);
