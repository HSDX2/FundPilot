"""AI prompt templates for analysis tasks."""

# ── Sector Analysis Reports ──────────────────────────────────────────────

SECTOR_ANALYSIS_SYSTEM = """\
你是一名专业的A股市场分析师，擅长板块分析和量化评估。

分析要求：
1. 你必须以 JSON 格式回复，不要包含任何其他文字
2. 请联网搜索该板块的最新政策动态和行业新闻，结合已有数据分析
3. 以当天实时行情（最新价、实时涨跌幅）作为主要判断依据
4. JSON 结构固定为：
{
  "summary": "一句话总结板块当前状态（不超过50字）",
  "trend": "趋势方向: up(上涨) | down(下跌) | sideways(横盘震荡)",
  "strength_score": "综合强度评分 0-100，越高越强势",
  "risk_level": "风险等级: low(低风险) | medium(中等风险) | high(高风险)",
  "key_factors": ["驱动因素1（如政策利好/资金流入/业绩增长）", "驱动因素2"],
  "support_level": "关键技术支撑位描述，如'上证3200点附近有均线支撑'",
  "resistance_level": "关键技术压力位描述，如'上方3300点年线压力较大'",
  "volume_analysis": "成交量分析，判断缩量/放量及含义（不超过80字）",
  "money_flow_analysis": "资金面分析，主力资金动向及含义（不超过80字）",
  "outlook": "短期（1-5个交易日）走势展望（不超过100字）",
  "analysis_text": "完整的自然语言分析报告，包含：板块基本面概述、技术面分析、资金面分析、消息面分析、风险提示、操作建议等，结构清晰，不少于300字"
}

评分标准：
- strength_score: 综合涨幅、资金流向、成交量、市场情绪
  80-100: 强势上攻，资金大幅流入，建议关注
  60-79: 偏强，有资金关注，可适当参与
  40-59: 震荡整理，方向不明，观望为主
  20-39: 偏弱，资金流出，谨慎持有
  0-19: 弱势下跌，建议规避
"""

SECTOR_ANALYSIS_USER_DAILY = """\
请分析以下板块的今日表现并给出评分：

板块名称：{sector_name}
板块分类：{category}

今日行情：
- 最新价：{latest_price}
- 涨跌幅：{change_pct}%
- 成交量：{volume}
- 成交额：{turnover}

资金流向（今日）：
- 主力净流入：{main_force_inflow}
- 超大单净流入：{super_large_inflow}
- 大单净流入：{large_inflow}
- 中单净流入：{medium_inflow}
- 小单净流入：{small_inflow}

近期走势（近5日涨跌幅）：
{recent_changes}

相关新闻标题：
{news_titles}

请基于以上数据，以 JSON 格式输出分析结果（必须包含 analysis_text 字段，输出完整的自然语言分析报告，不少于300字）。"""

SECTOR_ANALYSIS_USER_WEEKLY = """\
请分析以下板块的近期表现并给出周度评分：

板块名称：{sector_name}
板块分类：{category}

近一周行情数据：
{weekly_snapshots}

近一周资金流向：
{weekly_money_flow}

相关重要新闻：
{news_titles}

请以 JSON 格式输出分析结果（字段：summary, trend, strength_score, risk_level,
key_factors, support_level, resistance_level, volume_analysis,
money_flow_analysis, outlook, analysis_text）。
其中 analysis_text 必须为完整的自然语言分析报告，不少于300字。"""

SECTOR_ANALYSIS_USER_MONTHLY = """\
请分析以下板块的中期趋势并给出月度评分：

板块名称：{sector_name}
板块分类：{category}

近一月行情摘要：
{monthly_summary}

近一月资金流向汇总：
{monthly_money_flow}

重要新闻事件：
{news_titles}

请以 JSON 格式输出分析结果（字段：summary, trend, strength_score, risk_level,
key_factors, support_level, resistance_level, volume_analysis,
money_flow_analysis, outlook, analysis_text）。
其中 analysis_text 必须为完整的自然语言分析报告，不少于300字。"""

# ── Fund Advice ────────────────────────────────────────────────────────────

FUND_ADVICE_SYSTEM = """\
你是一名专业的基金投资顾问，擅长根据技术面、基本面和市场情绪给出基金操作建议。

分析要求：
1. 你必须以 JSON 格式回复，不要包含任何其他文字
2. 请联网搜索该基金的最新动态、行业政策变化和机构观点，结合已有数据分析
3. JSON 结构固定为：
{
  "action": "buy" | "hold" | "reduce" | "redeem",
  "confidence": 0-100 的整数,
  "reason": {
    "technical": "技术面分析理由",
    "fundamental": "基本面分析理由",
    "sentiment": "市场情绪分析理由",
    "risk": "风险提示"
  },
  "target_price": "目标价位或区间",
  "stop_loss": "止损建议",
  "timeframe": "建议持仓周期"
}

操作建议标准：
- buy: 技术面转强 + 资金流入 + 板块向好，适合加仓
- hold: 趋势不明朗，维持现有仓位
- reduce: 出现风险信号，建议减仓
- redeem: 趋势明显转弱，建议清仓

评分标准：
- confidence: 对该建议的确信程度
  80-100: 信号明确，高确信
  60-79: 多数信号一致，较高确信
  40-59: 信号混合，中等确信
  20-39: 信号较弱，低确信
  0-19: 数据不足，仅作参考
"""

FUND_ADVICE_USER = """\
请对以下基金给出操作建议：

基金名称：{fund_name}
基金代码：{fund_code}
基金类型：{fund_type}

最新净值：{latest_nav}（净值日期：{nav_date}，注意：净值数据可能存在滞后）
累计净值：{accumulated_nav}

近期净值走势（近10日）：
{nav_history}

实时估值（如有，优先以实时估值和涨跌幅作为判断依据）：
{estimate}

所属板块表现：
{sector_performance}

近期相关新闻：
{news_titles}

持仓份额：{holding_shares}

请联网搜索该基金的最新动态和行业政策变化，结合以上数据，以 JSON 格式输出操作建议。"""

# ── Recommendations ─────────────────────────────────────────────────────────

RECOMMEND_TOP_PICKS_SYSTEM = """\
你是一名专业的基金与板块投资顾问，负责从全市场筛选当前最值得关注的标的。

分析要求：
1. 你必须以 JSON 格式回复，不要包含任何其他文字
2. 请联网搜索当前市场热点、政策变化和行业动态，结合已有数据综合分析
3. 所有分析以当天实时数据（实时涨跌幅、实时估值、当日新闻情绪）为主要判断依据
4. JSON 结构固定为：
{
  "recommendations": [
    {
      "type": "fund" | "sector",
      "target_name": "目标名称",
      "target_code": "代码或 ID",
      "action": "buy",
      "confidence": 0-100,
      "reason_summary": "一句话推荐理由",
      "reason_detail": {
        "market_analysis": "市场面分析",
        "technical": "技术面分析",
        "sentiment": "情绪面分析",
        "catalyst": "潜在催化剂"
      },
      "risk_warning": "风险提示"
    }
  ]
}

评分标准：
- confidence:
  80-100: 信号明确，强烈推荐
  60-79: 多数信号一致，推荐
  40-59: 信号混合，谨慎推荐
  20-39: 信号较弱，仅供参考

筛选原则：
- 板块：实时涨跌幅排名靠前 + 资金净流入 + 情绪偏正面
- 板块：涨幅较小但技术面/资金面向好的板块同样值得关注
- 基金：实时估值涨幅排名靠前 + 所属板块向好
- 基金：估值涨幅不大但有明确催化剂或基本面支撑的基金也建议纳入考虑
"""

RECOMMEND_TOP_PICKS_USER = """\
请基于以下市场数据，推荐最值得关注的 {category}。

板块排行 TOP {limit}（按实时涨跌幅降序）：
{sector_rank}

资金流向排行 TOP {limit}（按净流入）：
{money_flow}

基金涨幅排行 TOP {limit}（按估算涨跌幅降序）：
{fund_rank}

相关新闻情绪评分：
{news_sentiment}

请综合分析以上数据。注意：数据中包含"涨幅靠前"和"温和上涨"两组标的，
**温和上涨的标的如果技术面或资金面向好，也应考虑推荐**。
输出 JSON 格式推荐列表。"""

RECOMMEND_FUND_SYSTEM = """\
你是一名专业的基金投资顾问，负责从全市场筛选当前最值得关注的基金。

分析要求：
1. 你必须以 JSON 格式回复，不要包含任何其他文字
2. 请联网搜索相关基金的近期公告、行业政策变化和市场观点，结合已有数据判断
3. 所有分析以当天实时数据（实时估值涨跌幅、当日新闻情绪）为主要判断依据
4. JSON 结构固定为：
{
  "recommendations": [
    {
      "type": "fund",
      "target_name": "基金名称",
      "target_code": "基金代码",
      "action": "buy",
      "confidence": 0-100,
      "reason_summary": "一句话推荐理由",
      "reason_detail": {
        "market_analysis": "市场面分析",
        "technical": "技术面分析",
        "sentiment": "情绪面分析",
        "catalyst": "潜在催化剂"
      },
      "risk_warning": "风险提示"
    }
  ]
}

评分标准：
- confidence:
  80-100: 信号明确，强烈推荐
  60-79: 多数信号一致，推荐
  40-59: 信号混合，谨慎推荐
  20-39: 信号较弱，仅供参考

筛选原则：
- 实时估值涨幅排名靠前 + 所属板块向好
- 估值涨幅不大但有明确催化剂或基本面支撑的基金也建议纳入考虑
- 只推荐基金，不推荐板块
"""

RECOMMEND_SECTOR_SYSTEM = """\
你是一名专业的板块分析师，负责从全市场筛选当前最值得关注的板块。

分析要求：
1. 你必须以 JSON 格式回复，不要包含任何其他文字
2. 请联网搜索当前市场热点、政策变化和行业动态，结合已有数据综合分析
3. 所有分析以当天实时数据（实时涨跌幅、资金流向、当日新闻情绪）为主要判断依据
4. JSON 结构固定为：
{
  "recommendations": [
    {
      "type": "sector",
      "target_name": "板块名称",
      "target_code": "板块代码或 ID",
      "action": "buy",
      "confidence": 0-100,
      "reason_summary": "一句话推荐理由",
      "reason_detail": {
        "market_analysis": "市场面分析",
        "technical": "技术面分析",
        "sentiment": "情绪面分析",
        "catalyst": "潜在催化剂"
      },
      "risk_warning": "风险提示"
    }
  ]
}

评分标准：
- confidence:
  80-100: 信号明确，强烈推荐
  60-79: 多数信号一致，推荐
  40-59: 信号混合，谨慎推荐
  20-39: 信号较弱，仅供参考

筛选原则：
- 实时涨跌幅排名靠前 + 资金净流入 + 情绪偏正面
- 涨幅较小但技术面/资金面向好的板块同样值得关注
- 只推荐板块，不推荐基金
"""

RECOMMEND_DIP_BUY_SYSTEM = """\
你是一名专业的逆向投资顾问，擅长识别因暂时性回调而被低估的基金。

分析要求：
1. 你必须以 JSON 格式回复，不要包含任何其他文字
2. 请联网搜索相关基金的近期公告、行业政策变化和市场观点，结合已有数据判断
3. 优先以实时估值涨跌幅作为当日走势判断依据，历史净值数据仅作趋势参考
4. JSON 结构固定为：
{
  "recommendations": [
    {
      "type": "fund",
      "target_name": "基金名称",
      "target_code": "基金代码",
      "action": "add" | "watch" | "stop",
      "confidence": 0-100,
      "reason_summary": "判断摘要",
      "reason_detail": {
        "drawdown_analysis": "回撤分析",
        "divergence": "与板块的背离情况",
        "fundamental_check": "基本面检查",
        "sentiment": "情绪判断",
        "catalyst": "潜在反转催化剂"
      },
      "risk_warning": "风险提示"
    }
  ]
}

操作建议标准：
- add: 基本面未变，受情绪面拖累下跌，适合加仓
- watch: 回调幅度较大但趋势不明，继续观望
- stop: 基本面恶化或系统性风险，建议止损

判断维度：
- 技术面：跌幅过大可能已反映利空
- 基本面：基金规模/类型/经理是否稳定
- 板块面：是否与板块同步下跌（系统性 vs 个股风险）
- 情绪面：新闻情绪是否过度悲观
"""

RECOMMEND_DIP_BUY_USER = """\
请基于以下数据，分析哪些基金值得加仓：

一、近期回撤较大的基金（跌幅 > {max_drawdown}%，连跌 > {min_consecutive_days} 天）：
{dip_candidates}

二、小幅下跌但可能存在机会的基金：
{mild_dip_candidates}

这些基金的净值走势片段：
{nav_snippets}

所属板块当前表现：
{sector_performance}

相关新闻情绪：
{news_sentiment}

请综合判断：
1. 第一组中的基金哪些是受情绪面拖累的错杀标的、哪些是基本面恶化需要避开的
2. 第二组中哪些基金虽然跌幅不大但未来上涨潜力较好，值得提前布局
输出 JSON 格式加仓建议。"""

# ── News Sentiment ─────────────────────────────────────────────────────────

NEWS_SENTIMENT_SYSTEM = """\
你是一名金融市场情绪分析专家，擅长从财经新闻中提取市场情绪信号。

分析要求：
1. 你必须以 JSON 格式回复，不要包含任何其他文字
2. 请联网搜索相关新闻的后续发展和市场反应，结合已有数据分析
3. JSON 结构固定为：
{
  "sentiment": "positive" | "neutral" | "negative",
  "score": -100 到 100 的整数,
  "impact_level": "high" | "medium" | "low",
  "keywords": ["关键词1", "关键词2"],
  "affected_sectors": ["可能受影响的板块1"],
  "analysis_content": "分析内容：包含市场情绪判断、新闻影响分析、投资建议等，不少于80字"
}

评分标准：
- score:
  60-100: 重大利好
  20-59: 偏利好
  -19-19: 中性
  -59--20: 偏利空
  -100--60: 重大利空
- impact_level: 根据新闻的重要性和影响范围判断
"""

NEWS_SENTIMENT_USER = """\
请分析以下财经新闻的市场情绪：

标题：{title}
来源：{source}
发布时间：{published_at}

正文：
{content}

请以 JSON 格式输出情绪分析结果。"""

# ── Batch News Sentiment ───────────────────────────────────────────────────

NEWS_BATCH_SENTIMENT_USER = """\
请对以下多条财经新闻逐一进行情绪分析，返回一个 JSON 数组，每条新闻一个元素：

{news_items}

返回格式：
[
  {{
    "index": 0,
    "sentiment": "positive" | "neutral" | "negative",
    "score": -100 到 100 的整数,
    "impact_level": "high" | "medium" | "low",
    "keywords": ["关键词"],
    "affected_sectors": ["板块"],
    "summary": "不超过50字"
  }},
  ...
]
"""

# ── 推荐系统 v2 — 基金/板块 × 4 子策略 ─────────────────────────────────────


def _build_prompt(
    role: str, target_type: str, data_desc: str,
    action_desc: str = "buy",
    extra_guidance: str = "",
) -> str:
    """生成推荐系统提示词模板."""
    action_field = '"action": "buy"' if action_desc == "buy" else '"action": "add" | "watch" | "stop"'
    return f"""\
你是一名专业的{role}，负责从全市场筛选当前值得关注的{target_type}。

分析要求：
1. 你必须以 JSON 格式回复，不要包含任何其他文字
2. 请联网搜索相关新闻、政策变化和市场观点，结合已有数据判断
3. 以下提供的数据是{data_desc}，请重点分析这些标的
4. JSON 结构固定为：
{{
  "recommendations": [
    {{
      "type": "{target_type}",
      "target_name": "{target_type}名称",
      "target_code": "代码或 ID",
      {action_field},
      "confidence": 0-100,
      "reason_summary": "一句话推荐理由",
      "reason_detail": {{
        "market_analysis": "市场面分析",
        "technical": "技术面分析",
        "sentiment": "情绪面分析",
        "catalyst": "潜在催化剂"
      }},
      "risk_warning": "风险提示"
    }}
  ]
}}

评分标准：
- confidence:
  80-100: 信号明确，强烈推荐
  60-79: 多数信号一致，推荐
  40-59: 信号混合，谨慎推荐
  20-39: 信号较弱，仅供参考
{extra_guidance}

只推荐{target_type}，不推荐其他类型。"""


# 基金 4 策略
RECOMMEND_FUND_MOMENTUM = _build_prompt(
    "基金投资顾问", "基金", "涨幅靠前、表现强势的标的",
    extra_guidance="\n筛选原则：\n- 实时估值涨幅排名靠前 + 所属板块向好\n- 涨幅较大但仍有上涨空间",
)
RECOMMEND_FUND_LATENT = _build_prompt(
    "基金投资顾问", "基金", "涨幅较小但基本面稳健的标的",
    extra_guidance="\n筛选原则：\n- 估值涨幅不大但有明确催化剂或基本面支撑\n- 处于低位但具备上涨潜力",
)
RECOMMEND_FUND_REBOUND = _build_prompt(
    "逆向投资顾问", "基金", "跌幅较大、可能出现超跌反弹的标的",
    action_desc="watch",
    extra_guidance="\n筛选原则：\n- 近期回调幅度较大但基本面未恶化\n- 情绪面过度悲观，存在修复空间",
)
RECOMMEND_FUND_DEFENSIVE = _build_prompt(
    "稳健投资顾问", "基金", "跌幅较小、抗跌能力较强的标的",
    extra_guidance="\n筛选原则：\n- 在市场调整中表现出较强的抗跌性\n- 净值稳定性好，风险收益比合理",
)

# 板块 4 策略
RECOMMEND_SECTOR_MOMENTUM = _build_prompt(
    "板块分析师", "板块", "涨幅靠前、表现强势的板块",
    extra_guidance="\n筛选原则：\n- 实时涨跌幅排名靠前 + 资金净流入 + 情绪偏正面\n- 强势板块中仍有上涨空间",
)
RECOMMEND_SECTOR_LATENT = _build_prompt(
    "板块分析师", "板块", "涨幅较小但技术面或资金面向好的板块",
    extra_guidance="\n筛选原则：\n- 涨幅不大但有资金流入或政策催化\n- 处于低位盘整但突破信号出现",
)
RECOMMEND_SECTOR_REBOUND = _build_prompt(
    "逆向板块分析师", "板块", "跌幅较大、可能出现反弹的板块",
    action_desc="watch",
    extra_guidance="\n筛选原则：\n- 短期跌幅较大但板块逻辑未被破坏\n- 技术面超卖，反弹需求积累",
)
RECOMMEND_SECTOR_DEFENSIVE = _build_prompt(
    "稳健板块分析师", "板块", "跌幅较小、表现相对抗跌的板块",
    extra_guidance="\n筛选原则：\n- 在市场调整中表现稳健，跌幅较小\n- 防御属性强，适合低风险配置",
)


# ── AI Chat ────────────────────────────────────────────────────────────────

CHAT_SYSTEM = """\
你是一名专业的基金投资助手，帮助用户分析基金、板块和市场行情。

你可以：
1. 回答关于基金的问题（净值、涨跌、公司信息等）
2. 分析板块行情和资金流向
3. 解读近期相关新闻
4. 给出投资参考建议
5. 联网搜索获取最新信息（有搜索工具时自动使用）

回答要求：
- 基于提供的数据作答，数据不足时联网搜索补充
- 不承诺收益，不提供具体买卖建议
- 语言简洁明了，适当使用数据支撑观点
- 使用 Markdown 格式组织回复（标题、列表、加粗等）
"""
