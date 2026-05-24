"""Sentiment composite indicator calculation.

Converts raw market sentiment data into a unified composite score (0-100).
"""



class SentimentService:
    """Compute composite market sentiment from raw indicators."""

    # Factor weights (sum = 1.0)
    WEIGHTS = {
        "limit_up_ratio": 0.15,         # 涨停比率
        "limit_down_ratio": 0.10,       # 跌停比率 (inverted)
        "broken_board_ratio": 0.10,     # 炸板率 (inverted)
        "north_bound": 0.15,            # 北向资金方向
        "margin_trend": 0.10,           # 融资余额变化
        "lhb_activity": 0.10,           # 龙虎榜活跃度
        "advance_decline": 0.10,        # 涨跌家数比
        "main_force": 0.10,             # 主力资金方向
        "market_cap": 0.05,             # 总市值趋势
        "pe_position": 0.05,            # PE 估值分位
    }

    @staticmethod
    def _safe_div(a, b, default=50.0):
        if b and b != 0:
            return a / b
        return default

    def compute_composite(self, raw: dict) -> float:
        """Compute composite sentiment score (0-100) from raw indicators.

        Each factor contributes 0-100, weighted by WEIGHTS.
        """
        scores: dict[str, float] = {}

        # 1. Limit-up ratio: up_count / (up + down)
        up = raw.get("limit_up_count") or 0
        down = raw.get("limit_down_count") or 0
        total_zt = up + down
        if total_zt > 0:
            scores["limit_up_ratio"] = min(100, (up / total_zt) * 100)
        else:
            scores["limit_up_ratio"] = 50

        # 2. Limit-down ratio (inverted): fewer down = higher score
        if total_zt > 0:
            scores["limit_down_ratio"] = max(0, (1 - down / total_zt) * 100)
        else:
            scores["limit_down_ratio"] = 50

        # 3. Broken board ratio (inverted): lower broken rate = higher score
        broken = raw.get("limit_up_broken_count") or 0
        if up > 0:
            broken_rate = broken / (up + broken)
            scores["broken_board_ratio"] = max(0, (1 - broken_rate) * 100)
        else:
            scores["broken_board_ratio"] = 50

        # 4. North-bound: net inflow direction and magnitude
        nb_inflow = raw.get("north_bound_net_inflow") or 0
        if nb_inflow > 5_000_000_000:
            scores["north_bound"] = 90
        elif nb_inflow > 1_000_000_000:
            scores["north_bound"] = 70
        elif nb_inflow > 0:
            scores["north_bound"] = 55
        elif nb_inflow > -1_000_000_000:
            scores["north_bound"] = 45
        elif nb_inflow > -5_000_000_000:
            scores["north_bound"] = 30
        else:
            scores["north_bound"] = 10

        # 5. Margin trend: positive balance = bullish
        margin_sse = raw.get("margin_balance_sse") or 0
        margin_szse = raw.get("margin_balance_szse") or 0
        scores["margin_trend"] = 50  # neutral by default
        _ = margin_sse + margin_szse  # reserved for historical comparison

        # 6. LHB activity: moderate activity = healthy
        lhb_count = raw.get("lhb_stock_count") or 0
        if 20 <= lhb_count <= 80:
            scores["lhb_activity"] = 60
        elif lhb_count > 80:
            scores["lhb_activity"] = 75
        elif lhb_count > 0:
            scores["lhb_activity"] = 40
        else:
            scores["lhb_activity"] = 50

        # 7. Advance/decline ratio (ADR)
        advance = raw.get("advance_count") or 0
        decline = raw.get("decline_count") or 0
        if advance + decline > 0:
            adr = advance / (advance + decline)
            scores["advance_decline"] = min(100, adr * 100)
        else:
            scores["advance_decline"] = 50

        # 8. Main force flow: positive = bullish
        mf_inflow = raw.get("main_force_net_inflow") or 0
        if mf_inflow > 1_000_000_000:
            scores["main_force"] = 80
        elif mf_inflow > 0:
            scores["main_force"] = 60
        elif mf_inflow > -1_000_000_000:
            scores["main_force"] = 40
        else:
            scores["main_force"] = 20

        # 9. Market cap trend: placeholder
        scores["market_cap"] = 50

        # 10. PE position: placeholder
        scores["pe_position"] = 50

        # Weighted composite
        composite = sum(
            scores.get(k, 50) * w for k, w in self.WEIGHTS.items()
        )
        return round(composite, 2)

    def compute_from_model(self, sentiment) -> float:
        """Compute composite score from a MarketSentiment ORM model."""
        raw = {
            "limit_up_count": (
                float(sentiment.limit_up_count)
                if sentiment.limit_up_count else 0
            ),
            "limit_down_count": (
                float(sentiment.limit_down_count)
                if sentiment.limit_down_count else 0
            ),
            "limit_up_broken_count": (
                float(sentiment.limit_up_broken_count)
                if sentiment.limit_up_broken_count else 0
            ),
            "north_bound_net_inflow": (
                float(sentiment.north_bound_net_inflow)
                if sentiment.north_bound_net_inflow else 0
            ),
            "margin_balance_sse": (
                float(sentiment.margin_balance_sse)
                if sentiment.margin_balance_sse else 0
            ),
            "margin_balance_szse": (
                float(sentiment.margin_balance_szse)
                if sentiment.margin_balance_szse else 0
            ),
            "lhb_stock_count": sentiment.lhb_stock_count or 0,
            "advance_count": sentiment.advance_count or 0,
            "decline_count": sentiment.decline_count or 0,
        }
        return self.compute_composite(raw)

    def interpret_score(self, score: float) -> str:
        """Interpret composite sentiment score."""
        if score >= 80:
            return "极度乐观"
        if score >= 65:
            return "偏乐观"
        if score >= 45:
            return "中性"
        if score >= 30:
            return "偏悲观"
        return "极度悲观"
