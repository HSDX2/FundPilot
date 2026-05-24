"""Collector service — orchestrates data fetching, transformation, and persistence."""

import logging
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import FUND_TYPE_PREFIX_MAP, FUND_TYPES_FOCUS
from app.integrations.akshare.fund_datasource import FundDataSource
from app.integrations.akshare.news_datasource import NewsDataSource
from app.integrations.akshare.sector_datasource import SectorDataSource
from app.integrations.akshare.sentiment_datasource import SentimentDataSource
from app.repositories.fund_repo import (
    FundEstimateRepo,
    FundNavRepo,
    FundRepo,
)
from app.repositories.news_repo import NewsArticleRepo, NewsSectorLinkRepo
from app.repositories.sector_repo import (
    SectorMoneyFlowRepo,
    SectorRepo,
    SectorSnapshotRepo,
)
from app.repositories.sentiment_repo import MarketSentimentRepo
from app.repositories.system_repo import CollectLogRepo

logger = logging.getLogger(__name__)

ALL_COLLECTORS = [
    "fund_list", "etf_list", "etf", "sector", "sector_list",
    "sector_daily", "sector_money_flow", "fund_estimate", "fund_nav", "news",
    "market_sentiment",
]


class CollectResult:
    """Result of a collection operation."""

    def __init__(
        self,
        records_added: int = 0,
        records_updated: int = 0,
        errors: list[str] | None = None,
    ):
        self.records_added = records_added
        self.records_updated = records_updated
        self.errors = errors or []

    def to_dict(self) -> dict[str, Any]:
        return {
            "records_added": self.records_added,
            "records_updated": self.records_updated,
            "errors": self.errors,
        }


def _default_task_state() -> dict[str, Any]:
    return {
        "status": "idle",
        "progress": 0,
        "total": 0,
        "message": "",
        "started_at": None,
    }


class CollectorService:
    """Orchestrates data collection from AkShare into the database."""

    _task_states: dict[str, dict[str, Any]] = {
        name: _default_task_state() for name in ALL_COLLECTORS
    }

    def __init__(
        self,
        fund_ds: FundDataSource | None = None,
        sector_ds: SectorDataSource | None = None,
        news_ds: NewsDataSource | None = None,
        sentiment_ds: SentimentDataSource | None = None,
        fund_repo: FundRepo | None = None,
        fund_nav_repo: FundNavRepo | None = None,
        fund_estimate_repo: FundEstimateRepo | None = None,
        sector_repo: SectorRepo | None = None,
        sector_snapshot_repo: SectorSnapshotRepo | None = None,
        sector_money_flow_repo: SectorMoneyFlowRepo | None = None,
        news_repo: NewsArticleRepo | None = None,
        news_sector_link_repo: NewsSectorLinkRepo | None = None,
        sentiment_repo: MarketSentimentRepo | None = None,
        collect_log_repo: CollectLogRepo | None = None,
    ):
        self.fund_ds = fund_ds or FundDataSource()
        self.sector_ds = sector_ds or SectorDataSource()
        self.news_ds = news_ds or NewsDataSource()
        self.sentiment_ds = sentiment_ds or SentimentDataSource()
        self.fund_repo = fund_repo
        self.fund_nav_repo = fund_nav_repo
        self.fund_estimate_repo = fund_estimate_repo
        self.sector_repo = sector_repo
        self.sector_snapshot_repo = sector_snapshot_repo
        self.sector_money_flow_repo = sector_money_flow_repo
        self.news_repo = news_repo
        self.news_sector_link_repo = news_sector_link_repo
        self.sentiment_repo = sentiment_repo
        self.collect_log_repo = collect_log_repo

    # ── Task state management ──

    def _get_session(self) -> AsyncSession | None:
        """Return the shared session from the first available repo."""
        for repo in (
            self.fund_repo, self.fund_nav_repo, self.fund_estimate_repo,
            self.sector_repo, self.sector_snapshot_repo, self.sector_money_flow_repo,
        ):
            if repo is not None:
                return repo.session
        return None

    @classmethod
    def request_stop(cls, collector_name: str) -> bool:
        """Request a running collector to stop. Returns False if not running."""
        state = cls._task_states.get(collector_name)
        if state is None or state["status"] != "running":
            return False
        state["status"] = "stopping"
        state["message"] = "Stop requested"
        return True

    @classmethod
    def get_task_status(cls, collector_name: str) -> dict[str, Any] | None:
        """Get the current status of a collector task."""
        return cls._task_states.get(collector_name)

    @classmethod
    def get_all_task_statuses(cls) -> dict[str, dict[str, Any]]:
        """Get statuses of all collector tasks."""
        return dict(cls._task_states)

    @classmethod
    def _start_task(cls, name: str, total: int, message: str = "") -> dict[str, Any]:
        """Mark a task as running and return its state dict."""
        state = cls._task_states[name]
        state["status"] = "running"
        state["progress"] = 0
        state["total"] = total
        state["message"] = message
        state["started_at"] = datetime.now(UTC)
        return state

    @classmethod
    def _finish_task(cls, name: str, message: str = "") -> None:
        """Mark a task as idle."""
        state = cls._task_states[name]
        state["status"] = "idle"
        state["message"] = message

    @classmethod
    def _should_stop(cls, name: str) -> bool:
        """Check if a stop has been requested for this task."""
        return cls._task_states[name]["status"] == "stopping"

    @classmethod
    def _update_progress(cls, name: str, progress: int, message: str = "") -> None:
        """Update progress for a running task."""
        state = cls._task_states[name]
        state["progress"] = progress
        if message:
            state["message"] = message

    async def _write_collect_log(
        self,
        collector_name: str,
        started_at: datetime,
        result: CollectResult,
        status: str = "success",
    ) -> None:
        """Persist a collect_logs record if a repo is available."""
        if self.collect_log_repo is None:
            return
        finished_at = datetime.now(UTC)
        duration_ms = int(
            (finished_at - started_at).total_seconds() * 1000
        )
        from app.models.system import CollectLog

        log_entry = CollectLog(
            collector_name=collector_name,
            status=status,
            records_added=result.records_added,
            records_updated=result.records_updated,
            error_message="; ".join(result.errors) if result.errors else None,
            duration_ms=duration_ms,
            started_at=started_at,
            finished_at=finished_at,
        )
        self.collect_log_repo.session.add(log_entry)
        await self.collect_log_repo.session.flush()

    # ── Fund collection ──

    async def collect_fund_list(self) -> CollectResult:
        """Fetch and persist all open-end funds."""
        started_at = datetime.now(UTC)
        self._start_task("fund_list", 1, "Fetching fund list from AkShare")
        result = CollectResult()
        try:
            raw = await self.fund_ds.fetch_fund_list()
            if not raw:
                result = CollectResult(errors=["No fund data returned from AkShare"])
                return result

            focus_prefixes = {
                FUND_TYPE_PREFIX_MAP[ft] for ft in FUND_TYPES_FOCUS
            }
            filtered = [
                r for r in raw
                if r.get("type")
                and any(
                    str(r["type"]).startswith(prefix) for prefix in focus_prefixes
                )
            ]

            if self.fund_repo is None:
                logger.warning("FundRepo not set, skipping DB write")
                result = CollectResult(records_added=len(filtered))
                return result

            added, updated = await self.fund_repo.batch_upsert(filtered)
            result = CollectResult(records_added=added, records_updated=updated)
            return result
        finally:
            status = "success" if not result.errors else "failed"
            self._finish_task("fund_list")
            await self._write_collect_log(
                "fund_list", started_at, result, status,
            )

    async def collect_etf_list(self) -> CollectResult:
        """Fetch ETF fund list and tag them as type=ETF."""
        started_at = datetime.now(UTC)
        self._start_task("etf_list", 1, "Fetching ETF list from AkShare")
        result = CollectResult()
        try:
            raw = await self.fund_ds.fetch_etf_list()
            if not raw:
                result = CollectResult(errors=["No ETF data returned from AkShare"])
                return result

            if self.fund_repo is None:
                result = CollectResult(records_added=len(raw))
                return result

            added, updated = await self.fund_repo.batch_upsert(raw)
            result = CollectResult(records_added=added, records_updated=updated)
            return result
        finally:
            status = "success" if not result.errors else "failed"
            self._finish_task("etf_list")
            await self._write_collect_log(
                "etf_list", started_at, result, status,
            )

    async def collect_etf_spot(self) -> CollectResult:
        """Fetch and persist ETF real-time spot data."""
        started_at = datetime.now(UTC)
        self._start_task("etf", 1, "Fetching ETF spot data")
        result = CollectResult()
        try:
            raw = await self.fund_ds.fetch_etf_spot()
            if not raw:
                result = CollectResult(errors=["No ETF spot data returned"])
                return result

            if self.fund_estimate_repo is None:
                result = CollectResult(records_added=len(raw))
                return result

            now = datetime.now()
            for record in raw:
                record["timestamp"] = now

            added, updated = await self.fund_estimate_repo.batch_upsert_estimates(raw)
            result = CollectResult(records_added=added, records_updated=updated)
            return result
        finally:
            status = "success" if not result.errors else "failed"
            self._finish_task("etf")
            await self._write_collect_log(
                "etf", started_at, result, status,
            )

    async def collect_estimates(self) -> CollectResult:
        """Fetch and persist real-time fund NAV estimates."""
        started_at = datetime.now(UTC)
        self._start_task("fund_estimate", 1, "Fetching fund estimates")
        result = CollectResult()
        try:
            raw = await self.fund_ds.fetch_estimate_all()
            if not raw:
                result = CollectResult(errors=["No estimate data returned"])
                return result

            if self.fund_estimate_repo is None:
                result = CollectResult(records_added=len(raw))
                return result

            now = datetime.now()
            for record in raw:
                record["timestamp"] = now

            added, updated = await self.fund_estimate_repo.batch_upsert_estimates(raw)
            result = CollectResult(records_added=added, records_updated=updated)
            return result
        finally:
            status = "success" if not result.errors else "failed"
            self._finish_task("fund_estimate")
            await self._write_collect_log(
                "fund_estimate", started_at, result, status,
            )

    async def collect_fund_nav_all(
        self, start_date: date | None = None,
    ) -> CollectResult:
        """Fetch and persist historical NAV for all funds.

        Each fund's NAV data is committed in its own transaction so that
        partial progress is preserved if the task is stopped or fails.
        """
        from datetime import timedelta

        started_at = datetime.now(UTC)
        result = CollectResult()
        if self.fund_repo is None or self.fund_nav_repo is None:
            result = CollectResult(errors=["FundRepo or FundNavRepo not set"])
            await self._write_collect_log(
                "fund_nav", started_at, result, "failed",
            )
            return result

        session = self._get_session()
        if session is None:
            result = CollectResult(errors=["No database session available"])
            await self._write_collect_log(
                "fund_nav", started_at, result, "failed",
            )
            return result

        funds, _ = await self.fund_repo.search(page=1, page_size=10000)
        if not funds:
            result = CollectResult(errors=["No funds in database to fetch NAV for"])
            await self._write_collect_log(
                "fund_nav", started_at, result, "failed",
            )
            return result

        if start_date is None:
            start_date = date.today() - timedelta(days=730)

        total = len(funds)
        state = self._start_task(
            "fund_nav", total, f"0/{total} funds processed",
        )

        added = 0
        updated = 0
        errors: list[str] = []
        stopped = False

        try:
            for i, fund in enumerate(funds):
                if self._should_stop("fund_nav"):
                    state["message"] = f"Stopped after {i}/{total} funds"
                    stopped = True
                    break

                try:
                    raw = await self.fund_ds.fetch_fund_nav(
                        fund.code, start_date=start_date,
                    )
                    if raw:
                        records: list[dict[str, Any]] = []
                        for row in raw:
                            nav_date_val = row.get("date")
                            if nav_date_val is None:
                                continue
                            records.append({
                                "fund_id": fund.id,
                                "date": nav_date_val,
                                "nav": row.get("nav"),
                                "daily_change_pct": row.get("daily_change_pct"),
                            })
                        if records:
                            a, u = await self.fund_nav_repo.batch_upsert_nav(records)
                            added += a
                            updated += u
                            await session.commit()
                except Exception as exc:
                    errors.append(f"{fund.code}: {exc}")

                self._update_progress(
                    "fund_nav", i + 1, f"{i + 1}/{total} funds",
                )

            result = CollectResult(
                records_added=added, records_updated=updated, errors=errors,
            )
            return result
        finally:
            status = "stopped" if stopped else ("failed" if errors else "success")
            self._finish_task(
                "fund_nav",
                f"Done: {added} added, {updated} updated, {len(errors)} errors",
            )
            await self._write_collect_log(
                "fund_nav", started_at, result, status,
            )

    # ── Sector collection ──

    async def collect_sector_list(self) -> CollectResult:
        """Fetch and persist industry + concept sector lists."""
        started_at = datetime.now(UTC)
        self._start_task("sector_list", 2, "Fetching sector lists")
        result = CollectResult()
        try:
            added = 0
            updated = 0
            errors: list[str] = []

            industry_raw = await self.sector_ds.fetch_industry_list()
            concept_raw = await self.sector_ds.fetch_concept_list()

            if self.sector_repo is None:
                result = CollectResult(
                    records_added=len(industry_raw) + len(concept_raw),
                )
                return result

            for row in industry_raw:
                row["category"] = "industry"
            a, u = await self.sector_repo.batch_upsert(industry_raw)
            added += a
            updated += u
            self._update_progress("sector_list", 1, "Industry sectors saved")

            for row in concept_raw:
                row["category"] = "concept"
            a, u = await self.sector_repo.batch_upsert(concept_raw)
            added += a
            updated += u
            self._update_progress("sector_list", 2, "Concept sectors saved")

            result = CollectResult(
                records_added=added, records_updated=updated, errors=errors,
            )
            return result
        finally:
            status = "success" if not result.errors else "failed"
            self._finish_task("sector_list")
            await self._write_collect_log(
                "sector_list", started_at, result, status,
            )

    async def collect_sector_realtime(self) -> CollectResult:
        """Fetch real-time sector data and save as snapshots."""
        started_at = datetime.now(UTC)
        self._start_task("sector", 1, "Fetching sector realtime data")
        result = CollectResult()
        try:
            raw = await self.sector_ds.fetch_board_realtime()
            if not raw:
                result = CollectResult(errors=["No sector realtime data returned"])
                return result

            if self.sector_repo is None or self.sector_snapshot_repo is None:
                result = CollectResult(records_added=len(raw))
                return result

            now = datetime.now()
            current_sectors = await self.sector_repo.get_all_active()
            sector_map = {s.name: s.id for s in current_sectors}

            records = []
            for row in raw:
                name = row.get("name")
                if not name or name not in sector_map:
                    continue
                records.append({
                    "sector_id": sector_map[name],
                    "timestamp": now,
                    "price": row.get("close") or row.get("price"),
                    "change_pct": row.get("change_pct"),
                    "turnover": row.get("total_market_cap"),
                })

            added, updated = await self.sector_snapshot_repo.batch_upsert_snapshots(
                records
            )
            result = CollectResult(records_added=added, records_updated=updated)
            return result
        finally:
            status = "success" if not result.errors else "failed"
            self._finish_task("sector")
            await self._write_collect_log(
                "sector", started_at, result, status,
            )

    async def collect_sector_daily_all(self) -> CollectResult:
        """Fetch daily historical data for all sectors and persist snapshots.

        Each sector's data is committed in its own transaction so that
        partial progress is preserved if the task is stopped or fails.
        """
        started_at = datetime.now(UTC)
        result = CollectResult()
        if self.sector_repo is None or self.sector_snapshot_repo is None:
            result = CollectResult(errors=["SectorRepo or SectorSnapshotRepo not set"])
            await self._write_collect_log(
                "sector_daily", started_at, result, "failed",
            )
            return result

        session = self._get_session()
        if session is None:
            result = CollectResult(errors=["No database session available"])
            await self._write_collect_log(
                "sector_daily", started_at, result, "failed",
            )
            return result

        sectors = await self.sector_repo.get_all_active()
        if not sectors:
            result = CollectResult(errors=["No sectors in database"])
            await self._write_collect_log(
                "sector_daily", started_at, result, "failed",
            )
            return result

        today = date.today().isoformat()
        total = len(sectors)
        state = self._start_task(
            "sector_daily", total, f"0/{total} sectors processed",
        )

        added = 0
        updated = 0
        errors: list[str] = []
        stopped = False

        try:
            for i, sector in enumerate(sectors):
                if self._should_stop("sector_daily"):
                    state["message"] = f"Stopped after {i}/{total} sectors"
                    stopped = True
                    break

                if not sector.code:
                    self._update_progress("sector_daily", i + 1)
                    continue

                try:
                    rows = await self.sector_ds.fetch_board_history(
                        sector.code,
                        start_date=today,
                        end_date=today,
                    )
                    for row in rows:
                        snap_date = row.get("date")
                        record = {
                            "sector_id": sector.id,
                            "timestamp": (
                                datetime.fromisoformat(snap_date)
                                if isinstance(snap_date, str)
                                else snap_date
                            ),
                            "price": row.get("close"),
                            "open": row.get("open"),
                            "high": row.get("high"),
                            "low": row.get("low"),
                            "change_pct": row.get("change_pct"),
                            "turnover": row.get("turnover"),
                            "volume": row.get("volume"),
                        }
                        a, u = await self.sector_snapshot_repo.batch_upsert_snapshots(
                            [record]
                        )
                        added += a
                        updated += u
                    await session.commit()
                except Exception as exc:
                    errors.append(f"{sector.name}({sector.code}): {exc}")

                self._update_progress(
                    "sector_daily", i + 1, f"{i + 1}/{total} sectors",
                )

            result = CollectResult(
                records_added=added, records_updated=updated, errors=errors,
            )
            return result
        finally:
            status = "stopped" if stopped else ("failed" if errors else "success")
            self._finish_task(
                "sector_daily",
                f"Done: {added} added, {updated} updated, {len(errors)} errors",
            )
            await self._write_collect_log(
                "sector_daily", started_at, result, status,
            )

    # ── Money flow ──

    async def collect_sector_money_flow(self) -> CollectResult:
        """Fetch sector fund flow data and persist to sector_money_flows."""
        started_at = datetime.now(UTC)
        result = CollectResult()
        if self.sector_repo is None or self.sector_money_flow_repo is None:
            result = CollectResult(
                errors=["SectorRepo or SectorMoneyFlowRepo not set"],
            )
            await self._write_collect_log(
                "sector_money_flow", started_at, result, "failed",
            )
            return result

        self._start_task(
            "sector_money_flow", 2, "Fetching sector fund flow",
        )
        try:
            current_sectors = await self.sector_repo.get_all_active()
            sector_map = {s.name: s.id for s in current_sectors}
            today_val = date.today()

            all_records = []
            for sector_type in ("行业资金流", "概念资金流"):
                raw = await self.sector_ds.fetch_sector_fund_flow(
                    indicator="今日", sector_type=sector_type,
                )
                for row in raw:
                    name = row.get("name")
                    if not name or name not in sector_map:
                        continue
                    all_records.append({
                        "sector_id": sector_map[name],
                        "date": today_val,
                        "main_force_net_inflow": row.get("main_force_net_inflow"),
                        "middle_net_inflow": row.get("middle_net_inflow"),
                        "retail_net_inflow": row.get("small_net_inflow"),
                    })

            if not all_records:
                result = CollectResult(errors=["No fund flow data matched sectors"])
                return result

            added, updated = await self.sector_money_flow_repo.batch_upsert(
                all_records
            )
            result = CollectResult(records_added=added, records_updated=updated)
            return result
        finally:
            status = "success" if not result.errors else "failed"
            self._finish_task("sector_money_flow")
            await self._write_collect_log(
                "sector_money_flow", started_at, result, status,
            )

    # ── Market sentiment ──

    async def collect_market_sentiment(self) -> CollectResult:
        """Collect daily market sentiment indicators and compute composite score."""
        from datetime import date as date_type

        from app.services.sentiment_service import SentimentService

        started_at = datetime.now(UTC)
        result = CollectResult()
        if self.sentiment_repo is None:
            result = CollectResult(errors=["MarketSentimentRepo not set"])
            await self._write_collect_log(
                "market_sentiment", started_at, result, "failed",
            )
            return result

        self._start_task(
            "market_sentiment", 9, "Fetching market sentiment data",
        )
        try:
            raw = await self.sentiment_ds.fetch_all_sentiment()
            today_val = date_type.today()

            # Parse raw data into record
            record: dict[str, Any] = {"date": today_val}

            # Limit-up pool
            limit_up = raw.get("limit_up") or []
            record["limit_up_count"] = len(limit_up)
            record["consecutive_limit_up_count"] = sum(
                1 for r in limit_up
                if (r.get("连板数") or 0) > 1
            )

            # Limit-down pool
            limit_down = raw.get("limit_down") or []
            record["limit_down_count"] = len(limit_down)

            # Limit-up broken (炸板)
            broken = raw.get("limit_up_broken") or []
            record["limit_up_broken_count"] = len(broken)

            # North-bound net inflow (latest day)
            nb_data = raw.get("north_bound") or []
            if nb_data:
                latest_nb = nb_data[-1]
                record["north_bound_net_inflow"] = latest_nb.get(
                    "当日成交净买额",
                )

            # Margin balance (latest day for each)
            margin_sse = raw.get("margin_sse") or []
            if margin_sse:
                record["margin_balance_sse"] = margin_sse[-1].get(
                    "融资余额",
                )
            margin_szse = raw.get("margin_szse") or []
            if margin_szse:
                record["margin_balance_szse"] = margin_szse[-1].get(
                    "融资余额",
                )

            # LHB stock count
            lhb_data = raw.get("lhb") or []
            record["lhb_stock_count"] = len(lhb_data)

            # Advance/decline
            a_spot = raw.get("a_spot") or []
            if a_spot:
                record["advance_count"] = sum(
                    1 for r in a_spot
                    if (r.get("涨跌幅") or 0) > 0
                )
                record["decline_count"] = sum(
                    1 for r in a_spot
                    if (r.get("涨跌幅") or 0) < 0
                )

            # Compute composite score
            sentiment_svc = SentimentService()
            record["composite_sentiment_score"] = sentiment_svc.compute_composite(
                {
                    "limit_up_count": record.get("limit_up_count") or 0,
                    "limit_down_count": record.get("limit_down_count") or 0,
                    "limit_up_broken_count": record.get("limit_up_broken_count") or 0,
                    "north_bound_net_inflow": record.get("north_bound_net_inflow") or 0,
                    "margin_balance_sse": record.get("margin_balance_sse") or 0,
                    "margin_balance_szse": record.get("margin_balance_szse") or 0,
                    "lhb_stock_count": record.get("lhb_stock_count") or 0,
                    "advance_count": record.get("advance_count") or 0,
                    "decline_count": record.get("decline_count") or 0,
                },
            )

            # Store extra raw data
            record["extra"] = {
                k: v for k, v in raw.items()
                if v is not None
            }

            await self.sentiment_repo.upsert(record)
            result = CollectResult(records_added=1)
            return result
        finally:
            status = "success" if not result.errors else "failed"
            self._finish_task("market_sentiment")
            await self._write_collect_log(
                "market_sentiment", started_at, result, status,
            )

    # ── News ──

    async def collect_news(
        self, sources: list[str] | None = None,
    ) -> CollectResult:
        """Fetch latest financial news and link to sectors by keyword match.

        Args:
            sources: News source names to collect. None = all sources.
        """
        started_at = datetime.now(UTC)
        result = CollectResult()
        if self.news_repo is None:
            result = CollectResult(errors=["NewsArticleRepo not set"])
            await self._write_collect_log(
                "news", started_at, result, "failed",
            )
            return result

        source_label = ",".join(sources) if sources else "all"
        self._start_task("news", 1, f"Fetching news from {source_label}")
        try:
            raw = await self.news_ds.fetch_all(sources=sources)
            if not raw:
                result = CollectResult(errors=["No news data returned"])
                return result

            added, updated = await self.news_repo.batch_upsert(raw)

            if self.sector_repo is not None and self.news_sector_link_repo is not None:
                sector_names = await self.sector_repo.get_all_names()
                if sector_names:
                    session = self._get_session()
                    for record in raw:
                        url = record.get("url")
                        if not url:
                            continue
                        text = str(record.get("title", "")) + str(
                            record.get("content", "")
                        )
                        article = await self.news_repo.find_by_url(url)
                        if article is None:
                            continue
                        for sector_id, sector_name in sector_names:
                            if sector_name in text:
                                from app.models.news import NewsSectorLink
                                session.add(
                                    NewsSectorLink(
                                        news_id=article.id,
                                        sector_id=sector_id,
                                        relevance_score=1.0,
                                    )
                                )
                    await session.flush()

            result = CollectResult(records_added=added, records_updated=updated)
            return result
        finally:
            status = "success" if not result.errors else "failed"
            self._finish_task("news")
            await self._write_collect_log(
                "news", started_at, result, status,
            )
