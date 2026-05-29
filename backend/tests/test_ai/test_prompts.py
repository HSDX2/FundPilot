"""Tests for AI prompt templates."""

from app.ai import prompts


class TestSectorAnalysisPrompts:
    def test_system_prompt_is_defined(self):
        assert "A股市场分析师" in prompts.SECTOR_ANALYSIS_SYSTEM
        assert "JSON" in prompts.SECTOR_ANALYSIS_SYSTEM

    def test_daily_prompt_has_placeholders(self):
        template = prompts.SECTOR_ANALYSIS_USER_DAILY
        assert "{sector_name}" in template
        assert "{change_pct}" in template
        assert "{main_force_inflow}" in template
        assert "{recent_changes}" in template
        assert "{news_titles}" in template

    def test_weekly_prompt_has_placeholders(self):
        template = prompts.SECTOR_ANALYSIS_USER_WEEKLY
        assert "{sector_name}" in template
        assert "{weekly_snapshots}" in template
        assert "{weekly_money_flow}" in template

    def test_monthly_prompt_has_placeholders(self):
        template = prompts.SECTOR_ANALYSIS_USER_MONTHLY
        assert "{sector_name}" in template
        assert "{monthly_summary}" in template
        assert "{monthly_money_flow}" in template

    def test_daily_prompt_formats(self):
        text = prompts.SECTOR_ANALYSIS_USER_DAILY.format(
            sector_name="新能源",
            category="概念板块",
            latest_price="3210.50",
            change_pct="+2.35",
            volume="123456",
            turnover="987654321",
            main_force_inflow="+5000",
            super_large_inflow="+2000",
            large_inflow="+3000",
            medium_inflow="-1000",
            small_inflow="-4000",
            recent_changes="- 05-20: +1.2%\n- 05-21: -0.5%",
            news_titles="- 新能源政策利好",
            weekly_snapshots="",
            weekly_money_flow="",
            monthly_summary="",
            monthly_money_flow="",
        )
        assert "新能源" in text
        assert "+2.35" in text
        assert "+5000" in text


class TestFundAdvicePrompts:
    def test_system_prompt_is_defined(self):
        assert "基金投资顾问" in prompts.FUND_ADVICE_SYSTEM
        assert "JSON" in prompts.FUND_ADVICE_SYSTEM
        assert "buy" in prompts.FUND_ADVICE_SYSTEM

    def test_user_prompt_has_placeholders(self):
        template = prompts.FUND_ADVICE_USER
        assert "{fund_name}" in template
        assert "{fund_code}" in template
        assert "{fund_type}" in template
        assert "{latest_nav}" in template
        assert "{nav_date}" in template
        assert "{nav_history}" in template
        assert "{estimate}" in template
        assert "{news_titles}" in template

    def test_user_prompt_formats(self):
        text = prompts.FUND_ADVICE_USER.format(
            fund_name="测试基金",
            fund_code="000001",
            fund_type="股票型",
            latest_nav="1.2345",
            nav_date="2026-05-29",
            accumulated_nav="2.3456",
            nav_history="- 2026-05-23: 净值 1.2345",
            estimate="估值: 1.2400, 涨跌: +0.45%",
            sector_performance="新能源: +2.1%",
            news_titles="- 利好消息",
            holding_shares="1000 份",
        )
        assert "测试基金" in text
        assert "000001" in text
        assert "1.2345" in text


class TestNewsSentimentPrompts:
    def test_system_prompt_is_defined(self):
        assert "情绪分析" in prompts.NEWS_SENTIMENT_SYSTEM
        assert "JSON" in prompts.NEWS_SENTIMENT_SYSTEM
        assert "positive" in prompts.NEWS_SENTIMENT_SYSTEM

    def test_user_prompt_has_placeholders(self):
        template = prompts.NEWS_SENTIMENT_USER
        assert "{title}" in template
        assert "{source}" in template
        assert "{content}" in template
        assert "{published_at}" in template

    def test_user_prompt_formats(self):
        text = prompts.NEWS_SENTIMENT_USER.format(
            title="央行降准释放流动性",
            source="东方财富",
            published_at="2026-05-23T10:00:00",
            content="中国人民银行决定下调存款准备金率...",
        )
        assert "央行降准" in text
        assert "东方财富" in text

    def test_batch_sentiment_prompt(self):
        assert "{news_items}" in prompts.NEWS_BATCH_SENTIMENT_USER
