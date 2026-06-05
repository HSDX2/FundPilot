"""Collector service — orchestrates data fetching, transformation, and persistence."""

import asyncio as aio
import logging
import math
from datetime import UTC, date, datetime
from typing import Any

from app.core.database import async_session_factory

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import FUND_TYPE_PREFIX_MAP, FUND_TYPES_FOCUS, FundType
from app.integrations.akshare.fund_datasource import FundDataSource
from app.integrations.akshare.news_datasource import NewsDataSource
from app.integrations.akshare.sector_datasource import SectorDataSource
from app.integrations.akshare.sentiment_datasource import SentimentDataSource
from app.integrations.base import DataSourceError
from app.repositories.fund_repo import (
    FundEstimateRepo,
    FundNavRepo,
    FundRepo,
)
from app.repositories.news_repo import NewsArticleRepo, NewsSectorLinkRepo
from app.repositories.sector_repo import (
    SectorMoneyFlowRepo,
    SectorRealtimeRepo,
    SectorRepo,
    SectorSnapshotRepo,
)
from app.repositories.sentiment_repo import MarketSentimentRepo
from app.models.news import NewsSectorLink
from app.repositories.system_repo import AIProviderRepo, CollectLogRepo, PromptSettingRepo

logger = logging.getLogger(__name__)

ALL_COLLECTORS = [
    "fund_list", "etf", "sector_list",
    "fund_nav_history", "fund_nav_daily",
    "news", "market_sentiment",
    "sector_batch_history", "sector_batch_daily",
    "fund_estimate", "sector_realtime",
    "news_sentiment",
    "recommend_top_picks", "recommend_dip_buy",
]


class TaskAlreadyRunningError(Exception):
    """Raised when trying to start a collector that is already running."""


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


def _safe_pct_float(value: object) -> float | None:
    """安全转为 float，处理百分号后缀."""
    if value is None:
        return None
    s = str(value).strip()
    if not s or s in ("---", "--", "—", "..."):
        return None
    if s.endswith("%"):
        s = s[:-1]
    try:
        return float(s.replace(",", ""))
    except (ValueError, TypeError):
        return None


def _default_task_state() -> dict[str, Any]:
    return {
        "status": "idle",
        "progress": 0,
        "total": 0,
        "message": "",
        "started_at": None,
    }


def _nav_worker(
    items: list[dict],
    start_date_str: str | None,
    per_fund: bool,
) -> tuple[list[dict], list[str], int, int]:
    """多进程 worker：在子进程中串行采集净值数据.

    每个子进程独立的 V8 上下文，可真正并行执行 AkShare 调用。
    返回 (nav_records, errors, added, updated) 供主进程合并。
    """
    import asyncio
    import uuid as _uuid
    from datetime import date as dt_date

    async def _run() -> tuple[list[dict], list[str], int, int]:
        from app.core.config import settings
        from sqlalchemy.ext.asyncio import (
            AsyncSession, async_sessionmaker, create_async_engine,
        )
        from sqlalchemy.pool import NullPool
        from app.repositories.fund_repo import FundNavRepo
        from app.integrations.akshare.fund_datasource import FundDataSource

        # 子进程独立 engine + NullPool，避免跨 event loop 冲突
        worker_engine = create_async_engine(
            settings.database_url, poolclass=NullPool,
        )
        worker_factory = async_sessionmaker(
            worker_engine, class_=AsyncSession, expire_on_commit=False,
        )

        ds = FundDataSource()
        start_date = dt_date.fromisoformat(start_date_str) if start_date_str else None
        all_records: list[dict] = []
        errors: list[str] = []
        added = 0
        updated = 0

        async with worker_factory() as session:
            nav_repo = FundNavRepo(session)

            for item in items:
                code = item["code"]
                fid = _uuid.UUID(item["fund_id"])

                try:
                    effective_start = start_date
                    if per_fund:
                        latest = await nav_repo.get_latest_nav_by_fund(fid)
                        if latest is None:
                            logger.warning(
                                "per_fund: no NAV found for %s (%s), fetching full history",
                                code, fid,
                            )
                        effective_start = (
                            None if latest is None else latest.date
                        )
                    raw = await asyncio.wait_for(
                        ds.fetch_fund_nav(
                            code, start_date=effective_start, skip_etf=True,
                        ),
                        timeout=70,
                    )
                except Exception as exc:
                    errors.append(f"{code}: {exc}")
                    continue

                records = [
                    {
                        "fund_id": fid,
                        "date": r["date"],
                        "nav": r.get("nav"),
                        "daily_change_pct": r.get("daily_change_pct"),
                    }
                    for r in raw if r.get("date") is not None
                ] if raw else []

                if records:
                    try:
                        a, u = await nav_repo.batch_upsert_nav(records)
                        added += a
                        updated += u
                        await session.commit()
                    except Exception as exc:
                        await session.rollback()
                        errors.append(f"{code}: DB {exc}")
                all_records.extend(records)

        try:
            await worker_engine.dispose()
        except Exception:
            pass
        return all_records, errors, added, updated

    return asyncio.run(_run())


def _chunk(items: list, n: int) -> list[list]:
    """将列表均匀分成 n 份."""
    size = max(1, len(items) // n)
    chunks = []
    for i in range(0, len(items), size):
        chunks.append(items[i:i + size])
    return chunks


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
        sector_realtime_repo: SectorRealtimeRepo | None = None,
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
        self.sector_realtime_repo = sector_realtime_repo
        self.news_repo = news_repo
        self.news_sector_link_repo = news_sector_link_repo
        self.sentiment_repo = sentiment_repo
        self.collect_log_repo = collect_log_repo

    # ── Task state management ──

    def _get_session(self) -> AsyncSession | None:
        """Return the shared session from the first available repo."""
        for repo in (
            self.fund_repo, self.fund_nav_repo,
            self.sector_repo, self.sector_snapshot_repo, self.sector_money_flow_repo,
        ):
            if repo is not None:
                return repo.session
        return None

    async def close(self) -> None:
        """Close the shared database session, releasing the connection back to the pool."""
        session = self._get_session()
        if session is not None:
            await session.close()

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
    def _check_not_running(cls, name: str) -> None:
        """Raise TaskAlreadyRunningError if the task is already in progress."""
        if cls._task_states[name]["status"] == "running":
            raise TaskAlreadyRunningError(
                f"{name} 正在执行中，不允许重复触发"
            )

    @classmethod
    def _start_task(cls, name: str, total: int, message: str = "") -> dict[str, Any]:
        """Mark a task as running and return its state dict.

        If already running, just update metadata (total/message).
        Otherwise initialise the state as a fresh run.
        """
        state = cls._task_states[name]
        if state["status"] == "running":
            if total > 0:
                state["total"] = total
            if message:
                state["message"] = message
            return state
        state["status"] = "running"
        state["progress"] = 0
        state["total"] = total
        state["message"] = message
        state["started_at"] = datetime.now(UTC)
        return state

    @classmethod
    def _finish_task(cls, name: str, message: str = "", errors: bool | str = False) -> str:
        """Mark a task as idle. Returns status string for log.

        errors=True → "failed", errors="partial" → "partial", else "success".
        """
        state = cls._task_states[name]
        if state["status"] == "stopping":
            status = "stopped"
        elif errors == "partial":
            status = "partial"
        elif errors:
            status = "failed"
        else:
            status = "success"
        state["status"] = "idle" if status not in ("partial",) else status
        state["message"] = message
        return status

    async def _rollback_session(self) -> None:
        """Rollback the shared session if it exists, recovering from DB errors."""
        session = self._get_session()
        if session is not None:
            try:
                await session.rollback()
            except Exception:
                pass

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
        try:
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
            await self.collect_log_repo.session.commit()
        except Exception:
            logger.exception(
                "Failed to write collect log for %s", collector_name,
            )

    # ── Fund collection ──

    @staticmethod
    def _resolve_fund_types(fund_type: str | None) -> set[str]:
        """将 fund_type 参数解析为类型集合。

        Args:
            fund_type: "etf" / "stock" / "mixed" / "index" / None（全部）
        """
        if not fund_type:
            return {"stock", "mixed", "index", "etf"}
        if fund_type == "etf":
            return {"etf"}
        try:
            ft = FundType(fund_type)
            return {ft.value}
        except ValueError:
            return {"stock", "mixed", "index", "etf"}

    async def collect_fund_list(
        self, fund_type: str | None = None,
    ) -> CollectResult:
        """采集并持久化基金/ETF 列表，按基金类型筛选，回填基本面信息。

        Args:
            fund_type: 基金类型筛选。None/""=全部类型, "etf"=仅ETF,
                       "stock"/"mixed"/"index"=对应类型。
        """
        started_at = datetime.now(UTC)
        self._start_task("fund_list", 1, "Fetching fund/ETF list from AkShare")
        result = CollectResult()
        try:
            selected_types = self._resolve_fund_types(fund_type)
            do_etf = "etf" in selected_types
            do_fund = any(t != "etf" for t in selected_types)

            all_records: list[dict[str, Any]] = []
            if do_etf:
                etf_raw = await self.fund_ds.fetch_etf_list()
                all_records.extend(etf_raw)
            if do_fund:
                fund_raw = await self.fund_ds.fetch_fund_list()
                ft_set = {
                    FUND_TYPE_PREFIX_MAP[ft]
                    for ft in selected_types if ft != "etf"
                }
                filtered = [
                    r for r in fund_raw
                    if r.get("type")
                    and any(str(r["type"]).startswith(p) for p in ft_set)
                ]
                all_records.extend(filtered)

            if not all_records:
                result = CollectResult(records_added=0)
                return result

            if self.fund_repo is None:
                logger.warning("FundRepo not set, skipping DB write")
                result = CollectResult(records_added=len(all_records))
                return result

            added, updated = await self.fund_repo.batch_upsert(all_records)
            result = CollectResult(records_added=added, records_updated=updated)

            # Backfill basic info for funds/ETFs missing company/manager data
            missing = await self.fund_repo.find_missing_basic_info(limit=500)
            if missing:
                self._start_task(
                    "fund_list", len(missing),
                    f"Backfilling basic info for {len(missing)} funds",
                )
                info_added = 0
                for i, fund in enumerate(missing):
                    info = await self.fund_ds.fetch_fund_basic_info_ths(fund.code)
                    if info is None:
                        info = await self.fund_ds.fetch_fund_basic_info(fund.code)
                    if info:
                        for key, value in info.items():
                            setattr(fund, key, value)
                        info_added += 1
                    else:
                        # 两个接口都无数据，标记为空防止下次重复查询
                        fund.company = "接口无法获取"
                    if (i + 1) % 20 == 0:
                        await self.fund_repo.session.flush()
                        await aio.sleep(0.3)  # rate-limit
                    self._update_progress(
                        "fund_list", i + 1,
                        f"Basic info {i + 1}/{len(missing)}",
                    )
                await self.fund_repo.session.flush()
                logger.info(
                    "Fund basic info backfill: %d/%d updated",
                    info_added, len(missing),
                )
        except DataSourceError as e:
            result = CollectResult(errors=[str(e)])
        except Exception as e:
            await self._rollback_session()
            logger.exception("Unexpected error in fund_list collector")
            result = CollectResult(errors=[str(e)])
        finally:
            status = self._finish_task(
                "fund_list", errors=bool(result.errors),
            )
            await self._write_collect_log(
                "fund_list", started_at, result, status,
            )
        return result

    async def collect_etf_spot(
        self, start_date: date | None = None,
    ) -> CollectResult:
        """拉取 ETF 实时行情并更新基金表中的 latest_price / latest_change_pct。

        start_date 为空时默认取当天。
        """
        started_at = datetime.now(UTC)
        self._start_task("etf", 1, "Fetching ETF spot data")
        result = CollectResult()
        try:
            raw = await self.fund_ds.fetch_etf_spot()
            if not raw:
                result = CollectResult(errors=["No ETF spot data returned"])
                return result

            if self.fund_repo is None:
                result = CollectResult(records_added=len(raw))
                return result

            session = self._get_session()
            if session is None:
                result = CollectResult(errors=["No database session available"])
                return result

            updated = 0
            for row in raw:
                code = row.get("code")
                if not code:
                    continue
                fund = await self.fund_repo.get_by_code(code)
                if fund is None:
                    continue
                price = row.get("price")
                pct = row.get("change_pct")
                if price is not None and not (isinstance(price, float) and math.isnan(price)):
                    fund.latest_price = float(price)
                if pct is not None and not (isinstance(pct, float) and math.isnan(pct)):
                    fund.latest_change_pct = float(pct)
                updated += 1

            await session.commit()
            result = CollectResult(records_added=0, records_updated=updated)
            return result
        except DataSourceError as e:
            result = CollectResult(errors=[str(e)])
        except Exception as e:
            await self._rollback_session()
            logger.exception("Unexpected error in etf collector")
            result = CollectResult(errors=[str(e)])
        finally:
            status = self._finish_task(
                "etf", errors=bool(result.errors),
            )
            await self._write_collect_log(
                "etf", started_at, result, status,
            )
        return result

    async def collect_fund_nav_all(
        self, start_date: date | None = None,
        task_name: str = "fund_nav_history",
        per_fund: bool = False,
        new_only: bool = False,
        worker_count: int = 8,
    ) -> CollectResult:
        """Fetch and persist historical NAV for all funds.

        If start_date is None, fetches all available history from the
        beginning (backfill mode).  If start_date is provided, fetches
        NAV from that date to today (incremental mode).

        When per_fund=True, each fund uses its own latest DB date as
        start_date (same logic as detail page"获取最新数据"), ignoring
        the global start_date parameter.

        Optimization: in incremental mode, skips funds that already have
        NAV data >= start_date.  Uses concurrent API calls (semaphore=10)
        to improve throughput while limiting server load.
        """
        started_at = datetime.now(UTC)
        result = CollectResult()
        if self.fund_repo is None or self.fund_nav_repo is None:
            result = CollectResult(errors=["FundRepo or FundNavRepo not set"])
            await self._write_collect_log(
                task_name, started_at, result, "failed",
            )
            self._finish_task(task_name, "Failed: no repo")
            return result

        session = self._get_session()
        if session is None:
            result = CollectResult(errors=["No database session available"])
            await self._write_collect_log(
                task_name, started_at, result, "failed",
            )
            self._finish_task(task_name, "Failed: no session")
            return result

        # 立即标记运行中，让前端轮询能看到进度
        self._start_task(task_name, 0, "Loading funds from database...")

        funds = await self.fund_repo.get_all_lean()
        if not funds:
            self._finish_task(task_name, "Done: no funds")
            result = CollectResult()
            await self._write_collect_log(
                task_name, started_at, result, "success",
            )
            return result

        # new_only 模式：只处理无净值记录的新基金
        if new_only:
            fund_ids = [f.id for f in funds]
            async with async_session_factory() as s:
                nav_repo_bulk = FundNavRepo(s)
                latest_dates = await nav_repo_bulk.get_latest_nav_dates(fund_ids)
            funds = [f for f in funds if f.id not in latest_dates]
            logger.info("new_only: %d/%d funds without NAV", len(funds), len(fund_ids))

        # per_fund 模式：过滤最新净值在 1 天内的基金，避免重复请求
        if per_fund:
            today = date.today()
            fund_ids = [f.id for f in funds]
            # 分批查询 latest_dates，避免大 IN 子句导致 PG 查询失效
            latest_dates: dict = {}
            BATCH = 2000
            async with async_session_factory() as s:
                nav_repo_bulk = FundNavRepo(s)
                for i in range(0, len(fund_ids), BATCH):
                    batch = fund_ids[i:i + BATCH]
                    batch_dates = await nav_repo_bulk.get_latest_nav_dates(batch)
                    latest_dates.update(batch_dates)
            logger.info(
                "per_fund: %d funds total, %d have latest_nav_date in DB",
                len(fund_ids), len(latest_dates),
            )
            funds = [
                f for f in funds
                if f.id not in latest_dates or (today - latest_dates[f.id]).days > 1
            ]
            logger.info(
                "per_fund: filtered to %d/%d funds needing update (1-day cutoff)",
                len(funds), len(fund_ids),
            )

        total = len(funds)
        self._start_task(task_name, total, f"Processing 0/{total} funds...")

        added = 0
        updated = 0
        errors: list[str] = []
        stopped = False

        if worker_count > 1 and total > 0:
            # ── 多进程模式：小批量 + as_completed 实现实时进度 ──
            from concurrent.futures import ProcessPoolExecutor

            items = [
                {"code": f.code, "fund_id": str(f.id)} for f in funds
            ]
            # 每块 ~50 只基金，约 1-2 分钟完成
            chunk_size = 50
            chunks = [
                items[i:i + chunk_size]
                for i in range(0, len(items), chunk_size)
            ]
            sd_str = start_date.isoformat() if start_date else None
            n_chunks = len(chunks)

            logger.info(
                "Multiprocess NAV: %d funds → %d workers × %d chunks × ~%d each",
                total, worker_count, n_chunks, chunk_size,
            )

            loop = aio.get_running_loop()
            completed_chunks = 0
            completed_funds = 0

            with ProcessPoolExecutor(max_workers=worker_count) as pool:
                futs = {
                    loop.run_in_executor(pool, _nav_worker, c, sd_str, per_fund): i
                    for i, c in enumerate(chunks)
                }
                for fut in aio.as_completed(futs):
                    if self._should_stop(task_name):
                        stopped = True
                        pool.shutdown(wait=False, cancel_futures=True)
                        # 清理子进程，避免产生孤儿
                        import signal as _sig
                        import multiprocessing as _mp
                        for _p in _mp.active_children():
                            _p.terminate()
                        break
                    try:
                        _records, worker_errors, a, u = await fut
                        added += a
                        updated += u
                        errors.extend(worker_errors)
                    except Exception as exc:
                        errors.append(f"chunk {futs[fut]}: {exc}")
                    completed_chunks += 1
                    completed_funds = min(total, completed_chunks * chunk_size)
                    self._update_progress(
                        task_name, completed_funds,
                        f"{completed_chunks}/{n_chunks} chunks ({completed_funds}/{total} funds)",
                    )

            # 确保多进程模式下所有子进程被清理
            import multiprocessing as _mp2
            for _p2 in _mp2.active_children():
                _p2.terminate()

        else:
            # ── 单进程串行模式 ──
            BATCH_SIZE = 500
            completed = 0

            for batch_start in range(0, total, BATCH_SIZE):
                if self._should_stop(task_name):
                    stopped = True
                    break

                batch = funds[batch_start:batch_start + BATCH_SIZE]

                async with async_session_factory() as batch_session:
                    nav_repo = FundNavRepo(batch_session)

                    for fund in batch:
                        if self._should_stop(task_name):
                            stopped = True
                            break
                        try:
                            effective_start = start_date
                            if per_fund:
                                latest = await nav_repo.get_latest_nav_by_fund(fund.id)
                                effective_start = None if latest is None else latest.date
                            raw = await aio.wait_for(
                                self.fund_ds.fetch_fund_nav(
                                    fund.code, start_date=effective_start,
                                ),
                                timeout=70,
                            )
                        except Exception as exc:
                            errors.append(f"{fund.code}: {exc}")
                            completed += 1
                            self._update_progress(
                                task_name, completed,
                                f"{completed}/{total} funds",
                            )
                            continue

                        records = [
                            {
                                "fund_id": fund.id,
                                "date": r["date"],
                                "nav": r.get("nav"),
                                "daily_change_pct": r.get("daily_change_pct"),
                            }
                            for r in raw if r.get("date") is not None
                        ] if raw else []

                        if records:
                            try:
                                a, u = await nav_repo.batch_upsert_nav(records)
                                added += a
                                updated += u
                                await batch_session.commit()
                            except Exception:
                                await batch_session.rollback()
                                errors.append(f"{fund.code}: DB persist failed")

                        completed += 1
                        self._update_progress(
                            task_name, completed,
                            f"{completed}/{total} funds",
                        )

        if stopped:
            errors.clear()
        result = CollectResult(
            records_added=added, records_updated=updated,
            errors=errors or None,
        )
        status = self._finish_task(
            task_name,
            f"Done: {added} added, {updated} updated, {len(errors)} errors",
            errors=bool(errors),
        )
        await self._write_collect_log(
            task_name, started_at, result, status,
        )
        return result

    async def collect_fund_nav_history(
        self, start_date: date | None = None,
        new_only: bool = False,
        worker_count: int = 8,
    ) -> CollectResult:
        """覆盖所有基金的历史净值和涨跌幅.

        new_only=True 时仅采集无净值记录的新基金。
        worker_count 控制多进程并发数（默认 8，最大 12）。
        """
        return await self.collect_fund_nav_all(
            start_date=start_date, task_name="fund_nav_history",
            new_only=new_only, worker_count=worker_count,
        )

    async def collect_fund_nav_daily(
        self, worker_count: int = 8,
    ) -> CollectResult:
        """从每个基金数据库最新净值日期往后增量采集（与详情页保持一致）。"""
        return await self.collect_fund_nav_all(
            task_name="fund_nav_daily", per_fund=True,
            worker_count=worker_count,
        )

    # ── Fund real-time estimate collection ──

    async def collect_fund_estimates(self) -> CollectResult:
        """采集全市场基金盘中实时估值，写入 fund_estimates 表（每基金一条最新记录）。"""
        started_at = datetime.now(UTC)
        task_name = "fund_estimate"
        result = CollectResult()
        if self.fund_estimate_repo is None:
            result = CollectResult(errors=["FundEstimateRepo not set"])
            await self._write_collect_log(task_name, started_at, result, "failed")
            self._finish_task(task_name, "Failed: no repo")
            return result

        self._start_task(task_name, 1, "Fetching estimates...")
        try:
            all_raw = await self.fund_ds.fetch_estimate_all()
            if not all_raw:
                result = CollectResult()
                self._finish_task(task_name, "Done: no data")
                await self._write_collect_log(task_name, started_at, result, "success")
                return result

            # 获取全量基金 code→id 映射（只查两列，不加载关联表）
            code_to_id = await self.fund_repo.get_code_id_map()

            records = []
            for raw in all_raw:
                fc = str(raw.get("fund_code", ""))
                fid = code_to_id.get(fc)
                if fid is None:
                    continue
                nav = raw.get("estimate_nav")
                if nav is None:
                    continue
                records.append({
                    "fund_id": fid,
                    "estimate_nav": _safe_pct_float(nav),
                    "estimate_change_pct": _safe_pct_float(raw.get("estimate_change_pct")),
                })

            added, updated = await self.fund_estimate_repo.batch_upsert(records)
            await self._get_session().commit()
            result = CollectResult(records_added=added, records_updated=updated)
        except Exception as e:
            await self._rollback_session()
            logger.exception("Fund estimate collection failed")
            result = CollectResult(errors=[str(e)])
        finally:
            self._finish_task(task_name, f"Done: {result.records_added} added, {result.records_updated} updated", errors=bool(result.errors))
            await self._write_collect_log(task_name, started_at, result, "success" if not result.errors else "failed")
        return result

    # ── Sector realtime collection ──

    async def collect_sectors_realtime(self) -> CollectResult:
        """采集行业板块实时行情，写入 sector_realtime 表。

        通过 THS summary API 批量获取。概念板块无批量实时 API，
        由详情页按需调用 fetch_sector_realtime 获取。
        """
        started_at = datetime.now(UTC)
        task_name = "sector_realtime"
        result = CollectResult()
        if self.sector_realtime_repo is None or self.sector_repo is None:
            result = CollectResult(errors=["Sector repo not set"])
            await self._write_collect_log(task_name, started_at, result, "failed")
            self._finish_task(task_name, "Failed: no repo")
            return result

        try:
            import akshare as ak
            loop = aio.get_running_loop()

            self._start_task(task_name, 1, "Fetching industry realtime...")

            industry_df = await loop.run_in_executor(
                None, ak.stock_board_industry_summary_ths,
            )
            industry_raw = industry_df.to_dict(orient="records") if industry_df is not None else []

            sectors = await self.sector_repo.get_all_active()
            name_to_id = {s.name: s.id for s in sectors if s.category == "industry"}

            records = []
            for row in industry_raw:
                name = row.get("板块")
                sid = name_to_id.get(name) if name else None
                if sid is None:
                    continue
                records.append({
                    "sector_id": sid,
                    "price": row.get("均价"),
                    "change_pct": row.get("涨跌幅"),
                    "volume": row.get("总成交量"),
                    "turnover": row.get("总成交额"),
                })

            added, updated = await self.sector_realtime_repo.batch_upsert(records)
            await self._get_session().commit()
            result = CollectResult(records_added=added, records_updated=updated)
        except Exception as e:
            await self._rollback_session()
            logger.exception("Sector realtime collection failed")
            result = CollectResult(errors=[str(e)])
        finally:
            self._finish_task(task_name, f"Done: {result.records_added + result.records_updated} sectors", errors=bool(result.errors))
            await self._write_collect_log(task_name, started_at, result, "success" if not result.errors else "failed")
        return result

    # ── News sentiment analysis ──

    async def collect_news_sentiment(
        self, limit: int = 50, force: bool = False,
        start_date: date | None = None,
        end_date: date | None = None,
        concurrency: int = 3,
    ) -> CollectResult:
        """对数据库中未分析的新闻执行 AI 情绪评分.

        start_date/end_date 限定新闻时间范围，concurrency 控制 AI 并发数。
        """
        from app.core.task_lock import sentiment_lock

        started_at = datetime.now(UTC)
        task_name = "news_sentiment"

        # 先检查锁，避免在 try/finally 中 return 导致写两次日志
        if not await sentiment_lock.try_acquire("news_sentiment"):
            result = CollectResult(errors=["新闻情绪分析任务正在执行中"])
            await self._write_collect_log(task_name, started_at, result, "failed")
            self._finish_task(task_name, "Already running")
            return result

        result = CollectResult()
        try:
            self._start_task(task_name, 0, "Loading analysis service...")

            async with async_session_factory() as s:
                from app.repositories.analysis_repo import AnalysisReportRepo, FundAdviceRepo
                from app.repositories.system_repo import AIProviderRepo, PromptSettingRepo
                from app.repositories.watchlist_repo import WatchedFundRepo
                from app.services.analysis_service import AnalysisService

                svc = AnalysisService(
                    ai_provider_repo=AIProviderRepo(s),
                    prompt_setting_repo=PromptSettingRepo(s),
                    analysis_report_repo=AnalysisReportRepo(s),
                    fund_advice_repo=FundAdviceRepo(s),
                    sector_repo=SectorRepo(s),
                    sector_snapshot_repo=SectorSnapshotRepo(s),
                    sector_money_flow_repo=SectorMoneyFlowRepo(s),
                    fund_repo=FundRepo(s),
                    fund_nav_repo=FundNavRepo(s),
                    fund_estimate_repo=FundEstimateRepo(s),
                    news_repo=NewsArticleRepo(s),
                    watchlist_repo=WatchedFundRepo(s),
                )

                self._start_task(task_name, 1, "Analyzing news sentiment...")
                count, batch_errors = await svc.batch_analyze_sentiment(
                    limit=limit, force=force,
                    start_date=start_date,
                    end_date=end_date,
                    concurrency=concurrency,
                )
                await s.commit()

            batch_errors = batch_errors or []
            result = CollectResult(records_added=count, records_updated=0, errors=batch_errors)
        except Exception as e:
            logger.exception("News sentiment analysis failed")
            result = CollectResult(errors=[str(e)])
        finally:
            sentiment_lock.release()
            self._finish_task(
                task_name,
                f"Done: {result.records_added} analyzed",
                errors=bool(result.errors),
            )
            await self._write_collect_log(
                task_name, started_at, result,
                "success" if not result.errors else "failed",
            )
        return result

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
            sector_fields = {"name", "code", "category", "description"}
            a, u = await self.sector_repo.batch_upsert([
                {k: v for k, v in row.items() if k in sector_fields}
                for row in industry_raw
            ])
            added += a
            updated += u
            self._update_progress("sector_list", 1, "Industry sectors saved")

            for row in concept_raw:
                row["category"] = "concept"
            a2, u2 = await self.sector_repo.batch_upsert([
                {k: v for k, v in row.items() if k in sector_fields}
                for row in concept_raw
            ])
            added += a2
            updated += u2
            self._update_progress("sector_list", 2, "Concept sectors saved")

            result = CollectResult(
                records_added=added, records_updated=updated, errors=errors,
            )
            return result
        except DataSourceError as e:
            result = CollectResult(errors=[str(e)])
        except Exception as e:
            await self._rollback_session()
            logger.exception("Unexpected error in sector_list collector")
            result = CollectResult(errors=[str(e)])
        finally:
            status = self._finish_task(
                "sector_list", errors=bool(result.errors),
            )
            await self._write_collect_log(
                "sector_list", started_at, result, status,
            )
        return result

    # ── Batch sector collection ────────────────────────────────────────

    async def collect_sectors_history(
        self, start_date: date | None = None,
        new_only: bool = False,
    ) -> CollectResult:
        """全量历史数据采集 — 对所有板块执行完整历史数据采集（OHLC + 资金流向）。

        如果 start_date 为空则获取全部历史数据。
        new_only=True 时仅采集无快照记录的板块。
        """
        from app.core.task_lock import sector_batch_lock

        started_at = datetime.now(UTC)
        result = CollectResult()

        if not await sector_batch_lock.try_acquire("sector_batch_history"):
            result = CollectResult(errors=["板块历史数据批量采集任务正在执行中"])
            return result

        try:
            if self.sector_repo is None:
                result = CollectResult(errors=["SectorRepo not set"])
                return result

            sectors = await self.sector_repo.get_all_active()

            # new_only：仅采集无快照 或 无资金流向的板块（缺失任一即补抽）
            if new_only:
                sector_ids = [s.id for s in sectors]
                with_snap: set[uuid.UUID] = set()
                with_mf: set[uuid.UUID] = set()
                if self.sector_snapshot_repo is not None:
                    snapshots = await self.sector_snapshot_repo.get_latest_per_sector(
                        sector_ids,
                    )
                    with_snap = {s.sector_id for s in snapshots}
                if self.sector_money_flow_repo is not None:
                    mf_ranges = await self.sector_money_flow_repo.get_all_date_ranges()
                    with_mf = set(mf_ranges.keys())
                sectors = [s for s in sectors if s.id not in with_snap or s.id not in with_mf]
                logger.info(
                    "new_only: %d/%d sectors (missing snap=%d, missing mf=%d)",
                    len(sectors), len(sector_ids),
                    sum(1 for s in sectors if s.id not in with_snap),
                    sum(1 for s in sectors if s.id not in with_mf),
                )

            total = len(sectors)
            if total == 0:
                return CollectResult()

            self._start_task(
                "sector_batch_history", total, f"0/{total} sectors",
            )

            now_str = date.today().isoformat()
            history_start = start_date.isoformat() if start_date else None
            flow_start = start_date if start_date else date(2000, 1, 1)
            sem = aio.Semaphore(8)
            from app.integrations.base import RateLimiter
            rate_limiter = RateLimiter(min_interval=0.5)
            db_lock = aio.Lock()
            added = 0
            updated = 0
            errors: list[str] = []
            completed = 0
            stopped = False

            async def _process_one(sector) -> None:
                nonlocal added, updated, completed, stopped
                if stopped or self._should_stop("sector_batch_history"):
                    return
                async with sem:
                    if stopped:
                        return
                    await rate_limiter.wait()

                    sec_added = 0
                    sec_updated = 0

                    # 1. OHLC 行情快照
                    if self.sector_snapshot_repo and self.sector_ds:
                        try:
                            history = await self.sector_ds.fetch_board_history(
                                name=sector.name,
                                category=sector.category or "industry",
                                start_date=history_start,
                                end_date=now_str,
                            )
                            if history:
                                records = []
                                for row in history:
                                    raw_date = row.get("date")
                                    if raw_date is None:
                                        continue
                                    ts = (
                                        date.fromisoformat(raw_date)
                                        if isinstance(raw_date, str)
                                        else raw_date
                                    )
                                    if ts.weekday() >= 5:
                                        continue
                                    # start_date 过滤：仅保留 start_date 及之后的数据
                                    if start_date and ts < start_date:
                                        continue
                                    records.append({
                                        "sector_id": sector.id,
                                        "timestamp": ts,
                                        "price": row.get("close"),
                                        "open": row.get("open"),
                                        "high": row.get("high"),
                                        "low": row.get("low"),
                                        "change_pct": None,
                                        "volume": row.get("volume"),
                                        "turnover": row.get("turnover"),
                                    })
                                records.sort(key=lambda r: r["timestamp"])
                                for i in range(len(records)):
                                    if i > 0 and records[i - 1].get("price") and records[i].get("price"):
                                        prev = float(records[i - 1]["price"])
                                        curr = float(records[i]["price"])
                                        if prev != 0:
                                            records[i]["change_pct"] = round(
                                                (curr - prev) / prev * 100, 4,
                                            )
                                # 补算第一条记录：从数据库取前日收盘价
                                if records and records[0].get("change_pct") is None and records[0].get("price") is not None:
                                    try:
                                        prev_snap = await self.sector_snapshot_repo.get_latest_before_date(
                                            sector.id, records[0]["timestamp"],
                                        )
                                        if prev_snap and prev_snap.price:
                                            prev_price = float(prev_snap.price)
                                            curr_price = float(records[0]["price"])
                                            if prev_price != 0:
                                                records[0]["change_pct"] = round(
                                                    (curr_price - prev_price) / prev_price * 100, 4,
                                                )
                                    except Exception:
                                        pass
                                async with db_lock:
                                    a, u = await self.sector_snapshot_repo.batch_upsert_snapshots(records)
                                    sec_added += a
                                    sec_updated += u
                        except Exception as exc:
                            async with db_lock:
                                errors.append(f"{sector.name}: OHLC - {exc}")

                    # 2. 资金流向
                    if self.sector_money_flow_repo and self.sector_ds:
                        try:
                            flows = await self.sector_ds.fetch_sector_fund_flow_range(
                                symbol=sector.name,
                                start_date=flow_start,
                            )
                            if flows:
                                records = []
                                for row in flows:
                                    row_date = row.get("date")
                                    if row_date is None:
                                        continue
                                    if hasattr(row_date, 'weekday') and row_date.weekday() >= 5:
                                        continue
                                    records.append({
                                        "sector_id": sector.id,
                                        "date": row_date,
                                        "main_force_net_inflow": row.get("main_force_net_inflow"),
                                        "retail_net_inflow": row.get("small_net_inflow"),
                                        "middle_net_inflow": row.get("middle_net_inflow"),
                                    })
                                async with db_lock:
                                    a, u = await self.sector_money_flow_repo.batch_upsert(
                                        records,
                                    )
                                    sec_added += a
                                    sec_updated += u
                        except Exception as exc:
                            async with db_lock:
                                errors.append(f"{sector.name}: 资金流向 - {exc}")

                    async with db_lock:
                        added += sec_added
                        updated += sec_updated
                        completed += 1
                        self._update_progress(
                            "sector_batch_history", completed,
                            f"{completed}/{total} sectors",
                        )
                        session = self._get_session()
                        if session:
                            try:
                                await session.commit()
                            except Exception:
                                await session.rollback()

            await aio.gather(*(
                _process_one(s) for s in sectors
            ))

            if self._should_stop("sector_batch_history"):
                stopped = True
            if stopped:
                errors.clear()

            result = CollectResult(
                records_added=added, records_updated=updated,
                errors=errors or None,
            )
            return result
        except Exception as e:
            await self._rollback_session()
            logger.exception("Unexpected error in sector_batch_history")
            result = CollectResult(
                records_added=0, records_updated=0,
                errors=[str(e)],
            )
        finally:
            status = self._finish_task(
                "sector_batch_history",
                f"Done: {result.records_added} added, {result.records_updated} updated, "
                f"{len(result.errors)} errors",
                errors=bool(result.errors),
            )
            await self._write_collect_log(
                "sector_batch_history", started_at, result, status,
            )
            sector_batch_lock.release()
        return result

    async def collect_sectors_daily(self, backfill_mf_detail: bool = True) -> CollectResult:
        """每日增量采集 — 对所有板块采集当日数据（OHLC + 资金流向）。

        每个板块独立检测数据库最新日期，从该日期往后采集（与详情页"获取最新数据"一致）。
        backfill_mf_detail=True 时使用 EM push2his API（含中单/散户三分类），
        backfill_mf_detail=False 时仅通过 THS 获取总额数据（避免 WAF 拦截问题）。
        """
        from app.core.task_lock import sector_batch_lock

        started_at = datetime.now(UTC)
        result = CollectResult()

        if not await sector_batch_lock.try_acquire("sector_batch_daily"):
            result = CollectResult(errors=["板块每日数据批量采集任务正在执行中"])
            return result

        try:
            if self.sector_repo is None:
                result = CollectResult(errors=["SectorRepo not set"])
                return result

            sectors = await self.sector_repo.get_all_active()
            total = len(sectors)
            if total == 0:
                return CollectResult()

            self._start_task(
                "sector_batch_daily", total, f"0/{total} sectors",
            )

            from app.integrations.base import RateLimiter

            sem = aio.Semaphore(8)
            rate_limiter = RateLimiter(min_interval=0.5)
            added = 0
            updated = 0
            errors: list[str] = []
            completed = 0
            stopped = False

            async def _process_one(sector) -> None:
                nonlocal added, updated, completed, stopped
                if stopped or self._should_stop("sector_batch_daily"):
                    return
                async with sem:
                    if stopped:
                        return
                    await rate_limiter.wait()

                    sec_added = 0
                    sec_updated = 0

                    # 每个协程独立 session，避免并发操作冲突
                    async with async_session_factory() as local_session:
                        snap_repo = SectorSnapshotRepo(local_session)
                        mf_repo = SectorMoneyFlowRepo(local_session)

                        # 检测该板块数据库最新日期
                        sector_latest: date | None = None
                        snap = await snap_repo.get_latest_by_sector(sector.id)
                        if snap and snap.timestamp:
                            sector_latest = snap.timestamp
                        from sqlalchemy import select as sa_select
                        from app.models.sector import SectorMoneyFlow
                        stmt = (
                            sa_select(SectorMoneyFlow.date)
                            .where(SectorMoneyFlow.sector_id == sector.id)
                            .order_by(SectorMoneyFlow.date.desc())
                            .limit(1)
                        )
                        result_row = await local_session.execute(stmt)
                        row = result_row.scalar_one_or_none()
                        if row:
                            sector_latest = max(sector_latest, row) if sector_latest else row

                        # 资金流向起始日期取中单/散户有值的最新日期
                        mf_latest_complete = await mf_repo.get_latest_complete_date(sector.id)

                        start_sd = sector_latest.isoformat() if sector_latest else None
                        mf_start = mf_latest_complete if mf_latest_complete else (sector_latest if sector_latest else date(2000, 1, 1))
                        now_str = date.today().isoformat()

                    # 1. OHLC 行情快照
                    if self.sector_ds:
                        try:
                            history = await self.sector_ds.fetch_board_history(
                                name=sector.name,
                                category=sector.category or "industry",
                                start_date=start_sd,
                                end_date=now_str,
                            )
                            if history:
                                records = []
                                for row in history:
                                    raw_date = row.get("date")
                                    if raw_date is None:
                                        continue
                                    ts = (
                                        date.fromisoformat(raw_date)
                                        if isinstance(raw_date, str)
                                        else raw_date
                                    )
                                    if ts.weekday() >= 5:
                                        continue
                                    if sector_latest and ts < sector_latest:
                                        continue
                                    records.append({
                                        "sector_id": sector.id,
                                        "timestamp": ts,
                                        "price": row.get("close"),
                                        "open": row.get("open"),
                                        "high": row.get("high"),
                                        "low": row.get("low"),
                                        "change_pct": None,
                                        "volume": row.get("volume"),
                                        "turnover": row.get("turnover"),
                                    })
                                records.sort(key=lambda r: r["timestamp"])
                                for i in range(len(records)):
                                    if i > 0 and records[i - 1].get("price") and records[i].get("price"):
                                        prev = float(records[i - 1]["price"])
                                        curr = float(records[i]["price"])
                                        if prev != 0:
                                            records[i]["change_pct"] = round(
                                                (curr - prev) / prev * 100, 4,
                                            )
                                # 补算第一条记录
                                if records and records[0].get("change_pct") is None and records[0].get("price") is not None:
                                    try:
                                        prev_snap = await snap_repo.get_latest_before_date(
                                            sector.id, records[0]["timestamp"],
                                        )
                                        if prev_snap and prev_snap.price:
                                            prev_price = float(prev_snap.price)
                                            curr_price = float(records[0]["price"])
                                            if prev_price != 0:
                                                records[0]["change_pct"] = round(
                                                    (curr_price - prev_price) / prev_price * 100, 4,
                                                )
                                    except Exception:
                                        pass
                                a, u = await snap_repo.batch_upsert_snapshots(records)
                                sec_added += a
                                sec_updated += u
                        except Exception as exc:
                            errors.append(f"{sector.name}: OHLC - {exc}")

                    # 2. 资金流向
                    if self.sector_ds:
                        try:
                            if backfill_mf_detail:
                                flows = await self.sector_ds.fetch_sector_fund_flow_range(
                                    symbol=sector.name, start_date=mf_start,
                                )
                                if flows:
                                    records = []
                                    for row in flows:
                                        row_date = row.get("date")
                                        if row_date is None:
                                            continue
                                        if row_date.weekday() >= 5:
                                            continue
                                        if sector_latest and row_date < sector_latest:
                                            continue
                                        records.append({
                                            "sector_id": sector.id,
                                            "date": row_date,
                                            "main_force_net_inflow": row.get("main_force_net_inflow"),
                                            "retail_net_inflow": row.get("small_net_inflow"),
                                            "middle_net_inflow": row.get("middle_net_inflow"),
                                        })
                                    a, u = await mf_repo.batch_upsert(records)
                                    sec_added += a
                                    sec_updated += u
                            else:
                                from datetime import datetime, timezone, timedelta
                                beijing_hour = datetime.now(timezone(timedelta(hours=8))).hour
                                mf_effective_date = date.today()
                                if beijing_hour < 15:
                                    mf_effective_date = mf_effective_date - timedelta(days=1)
                                ths_data = await self.sector_ds._fetch_thz_fund_flow_today(sector.name)
                                if ths_data:
                                    records = [{
                                        "sector_id": sector.id,
                                        "date": mf_effective_date,
                                        "main_force_net_inflow": ths_data[0].get("main_force_net_inflow"),
                                        "retail_net_inflow": None,
                                        "middle_net_inflow": None,
                                    }]
                                    a, u = await mf_repo.batch_upsert(records)
                                    sec_added += a
                                    sec_updated += u
                        except Exception as exc:
                            errors.append(f"{sector.name}: 资金流向 - {exc}")

                        try:
                            await local_session.commit()
                        except Exception:
                            await local_session.rollback()

                    added += sec_added
                    updated += sec_updated
                    completed += 1
                    self._update_progress(
                        "sector_batch_daily", completed,
                        f"{completed}/{total} sectors",
                    )

            await aio.gather(*(
                _process_one(s) for s in sectors
            ))

            if self._should_stop("sector_batch_daily"):
                stopped = True
            if stopped:
                errors.clear()

            result = CollectResult(
                records_added=added, records_updated=updated,
                errors=errors or None,
            )
            return result
        except Exception as e:
            await self._rollback_session()
            logger.exception("Unexpected error in sector_batch_daily")
            result = CollectResult(
                records_added=0, records_updated=0,
                errors=[str(e)],
            )
        finally:
            has_records = result.records_added > 0 or result.records_updated > 0
            has_errors = bool(result.errors)
            status = self._finish_task(
                "sector_batch_daily",
                f"Done: {result.records_added} added, {result.records_updated} updated, "
                f"{len(result.errors)} errors",
                errors="partial" if (has_records and has_errors) else has_errors,
            )
            await self._write_collect_log(
                "sector_batch_daily", started_at, result, status,
            )
            sector_batch_lock.release()
        return result

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

            # 清理 numeric 字段中的 NaN（PostgreSQL 不支持）
            import math
            for _key in list(record.keys()):
                _v = record[_key]
                if isinstance(_v, float) and math.isnan(_v):
                    record[_key] = None

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

            # Store extra raw data（递归转换 date/nan 兼容 JSONB）
            import math

            def _json_safe(val):
                if isinstance(val, date_type):
                    return val.isoformat()
                if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
                    return None
                if isinstance(val, dict):
                    return {k: _json_safe(v) for k, v in val.items()}
                if isinstance(val, list):
                    return [_json_safe(v) for v in val]
                return val

            record["extra"] = {
                k: _json_safe(v) for k, v in raw.items()
                if v is not None
            }

            await self.sentiment_repo.upsert(record)
            await self._get_session().commit()
            result = CollectResult(records_added=1)
            return result
        except DataSourceError as e:
            result = CollectResult(errors=[str(e)])
        except Exception as e:
            await self._rollback_session()
            logger.exception("Unexpected error in market_sentiment collector")
            result = CollectResult(errors=[str(e)])
        finally:
            status = self._finish_task(
                "market_sentiment", errors=bool(result.errors),
            )
            await self._write_collect_log(
                "market_sentiment", started_at, result, status,
            )
        return result

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

            # 检查是否在 fetch_all 期间收到停止请求
            if self._should_stop("news"):
                result = CollectResult(errors=["Task stopped by user"])
                return result

            raw = [r for r in raw if r.get("title")]
            if not raw:
                result = CollectResult(errors=["No news data returned"])
                return result

            # 再次检查停止请求（title 过滤后）
            if self._should_stop("news"):
                result = CollectResult(errors=["Task stopped by user"])
                return result

            added, updated = await self.news_repo.batch_upsert(raw)

            if self.sector_repo is not None and self.news_sector_link_repo is not None:
                sector_names = await self.sector_repo.get_all_names()
                if sector_names:
                    session = self._get_session()
                    linked: set[tuple[str, str]] = set()
                    sp = await session.begin_nested()
                    try:
                        with session.no_autoflush:
                            for record in raw:
                                # 每处理 50 条新闻检查一次停止请求
                                if len(linked) % 50 == 0 and self._should_stop("news"):
                                    break
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
                                    if self._should_stop("news"):
                                        break
                                    key = (str(article.id), str(sector_id))
                                    if sector_name in text and key not in linked:
                                        session.add(
                                            NewsSectorLink(
                                                news_id=article.id,
                                                sector_id=sector_id,
                                                relevance_score=1.0,
                                            )
                                        )
                                        linked.add(key)
                            if linked:
                                await session.flush()
                                await sp.commit()
                            else:
                                await sp.rollback()
                    except Exception:
                        await sp.rollback()

            result = CollectResult(records_added=added, records_updated=updated)
            return result
        except DataSourceError as e:
            result = CollectResult(errors=[str(e)])
        except Exception as e:
            await self._rollback_session()
            logger.exception("Unexpected error in news collector")
            result = CollectResult(errors=[str(e)])
        finally:
            status = self._finish_task(
                "news", errors=bool(result.errors),
            )
            await self._write_collect_log(
                "news", started_at, result, status,
            )
        return result

    # ── AI Recommendation ──

    async def collect_recommend_top_picks(
        self, limit: int = 8, concurrency: int = 2,
    ) -> CollectResult:
        """运行综合推荐，结果存入 recommendations 表."""
        started_at = datetime.now(UTC)
        task_name = "recommend_top_picks"
        result = CollectResult()
        self._start_task(task_name, 1, "Running top picks recommendation...")

        try:
            async with async_session_factory() as s:
                from app.repositories.analysis_repo import RecommendationRepo
                from app.services.recommendation_service import RecommendationService

                svc = RecommendationService(
                    ai_provider_repo=AIProviderRepo(s),
                    prompt_setting_repo=PromptSettingRepo(s),
                    fund_repo=FundRepo(s),
                    fund_nav_repo=FundNavRepo(s),
                    sector_repo=SectorRepo(s),
                    sector_snapshot_repo=SectorSnapshotRepo(s),
                    sector_money_flow_repo=SectorMoneyFlowRepo(s),
                    news_repo=NewsArticleRepo(s),
                    recommendation_repo=RecommendationRepo(s),
                )
                items = await svc.generate(category="fund", mode="momentum", limit=limit)
                await s.commit()

            result = CollectResult(records_added=len(items), records_updated=0)
        except Exception as e:
            logger.exception("Top picks recommendation failed")
            result = CollectResult(errors=[str(e)])
        finally:
            self._finish_task(task_name, f"Done: {result.records_added} items", errors=bool(result.errors))
            await self._write_collect_log(task_name, started_at, result, "success" if not result.errors else "failed")
        return result

    async def collect_recommend_dip_buy(
        self, limit: int = 8, max_drawdown: float = 5.0,
        min_consecutive_days: int = 3, concurrency: int = 2,
    ) -> CollectResult:
        """运行加仓推荐，结果存入 recommendations 表."""
        started_at = datetime.now(UTC)
        task_name = "recommend_dip_buy"
        result = CollectResult()
        self._start_task(task_name, 1, "Running dip buy recommendation...")

        try:
            async with async_session_factory() as s:
                from app.repositories.analysis_repo import RecommendationRepo
                from app.services.recommendation_service import RecommendationService

                svc = RecommendationService(
                    ai_provider_repo=AIProviderRepo(s),
                    prompt_setting_repo=PromptSettingRepo(s),
                    fund_repo=FundRepo(s),
                    fund_nav_repo=FundNavRepo(s),
                    sector_repo=SectorRepo(s),
                    sector_snapshot_repo=SectorSnapshotRepo(s),
                    sector_money_flow_repo=SectorMoneyFlowRepo(s),
                    news_repo=NewsArticleRepo(s),
                    recommendation_repo=RecommendationRepo(s),
                )
                items = await svc.generate(
                    category="fund", mode="rebound",
                    limit=limit,
                )
                await s.commit()

            result = CollectResult(records_added=len(items), records_updated=0)
        except Exception as e:
            logger.exception("Dip buy recommendation failed")
            result = CollectResult(errors=[str(e)])
        finally:
            self._finish_task(task_name, f"Done: {result.records_added} items", errors=bool(result.errors))
            await self._write_collect_log(task_name, started_at, result, "success" if not result.errors else "failed")
        return result
