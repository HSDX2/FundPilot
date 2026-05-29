"""Fund business logic — data transformation and orchestration."""

import uuid
from datetime import date, datetime, timedelta, timezone

from app.core.constants import FUND_TYPE_PREFIX_MAP
from app.integrations.akshare.fund_datasource import FundDataSource
from app.repositories.fund_repo import FundEstimateRepo, FundNavRepo, FundRepo
from app.models.fund import FundNav
from app.schemas.fund import (
    FundListData,
    FundNavListData,
    FundNavResponse,
    FundResponse,
)


class FundService:
    """Fund-related business logic."""

    def __init__(
        self,
        fund_repo: FundRepo,
        fund_nav_repo: FundNavRepo | None = None,
        fund_estimate_repo: FundEstimateRepo | None = None,
        fund_datasource: FundDataSource | None = None,
    ):
        self._fund_repo = fund_repo
        self._nav_repo = fund_nav_repo
        self._estimate_repo = fund_estimate_repo
        self._fund_ds = fund_datasource

    async def search_funds(
        self,
        name: str | None = None,
        type_: str | None = None,
        company: str | None = None,
        page: int = 1,
        page_size: int = 20,
        sort_by: str | None = None,
        sort_order: str = "desc",
        watched_only: bool = False,
    ) -> FundListData:
        db_type = None
        if type_:
            db_type = FUND_TYPE_PREFIX_MAP.get(type_)

        items, total = await self._fund_repo.search(
            name=name,
            type_=db_type,
            company=company,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
            watched_only=watched_only,
        )
        # Attach latest NAV data
        fund_ids = [f.id for f in items]
        nav_map: dict[uuid.UUID, FundNav] = {}
        if fund_ids and self._nav_repo is not None:
            nav_map = await self._nav_repo.get_latest_navs(fund_ids)

        # Attach latest fund_estimates
        est_map: dict[uuid.UUID, Any] = {}
        if fund_ids and self._estimate_repo is not None:
            from app.models.fund import FundEstimate
            from sqlalchemy import select as sa_select
            stmt = sa_select(FundEstimate).where(
                FundEstimate.fund_id.in_(fund_ids),
            )
            result = await self._fund_repo.session.execute(stmt)
            for row in result.scalars():
                est_map[row.fund_id] = row

        fund_responses: list[FundResponse] = []
        for f in items:
            resp = FundResponse.model_validate(f)
            nav = nav_map.get(f.id)
            if nav is not None:
                resp.latest_nav_date = nav.date
                resp.latest_nav = nav.nav
                resp.latest_nav_change_pct = nav.daily_change_pct
            est = est_map.get(f.id)
            if est is not None and est.estimate_nav is not None:
                resp.estimate_nav = est.estimate_nav
                resp.estimate_change_pct = est.estimate_change_pct
            elif f.latest_price is not None:
                # ETF 等有实时市价的基金，用 latest_price 作为估值
                resp.estimate_nav = f.latest_price
                resp.estimate_change_pct = f.latest_change_pct
            fund_responses.append(resp)

        return FundListData(
            items=fund_responses,
            total=total,
            page=page,
            page_size=page_size,
        )

    async def get_fund_by_code(self, code: str) -> FundResponse | None:
        fund = await self._fund_repo.get_by_code(code)
        if fund is None:
            return None
        # Lazy backfill: fetch from API if info missing or stale (24h+ old)
        if self._fund_ds is not None:
            needs_refresh = fund.company is None
            if not needs_refresh and fund.updated_at is not None:
                age = datetime.now(timezone.utc) - fund.updated_at
                needs_refresh = age > timedelta(hours=24)
            if needs_refresh:
                try:
                    info = await self._fund_ds.fetch_fund_basic_info_ths(code)
                    if info is None:
                        info = await self._fund_ds.fetch_fund_basic_info(code)
                    if info:
                        for key, value in info.items():
                            setattr(fund, key, value)
                        await self._fund_repo.session.commit()
                except Exception:
                    pass  # non-critical, serve cached data
        resp = FundResponse.model_validate(fund)

        # Attach latest NAV data
        if self._nav_repo is not None:
            latest_nav = await self._nav_repo.get_latest_nav_by_fund(fund.id)
            if latest_nav is not None:
                resp.latest_nav_date = latest_nav.date
                resp.latest_nav = latest_nav.nav
                resp.latest_nav_change_pct = latest_nav.daily_change_pct

        # Attach latest estimate data
        if self._estimate_repo is not None:
            est = await self._estimate_repo.get_by_fund(fund.id)
            if est is not None and est.estimate_nav is not None:
                resp.estimate_nav = est.estimate_nav
                resp.estimate_change_pct = est.estimate_change_pct
            elif fund.latest_price is not None:
                # ETF 等有实时市价的基金，用 latest_price 作为估值
                resp.estimate_nav = fund.latest_price
                resp.estimate_change_pct = fund.latest_change_pct

        return resp

    async def get_fund_nav_history(
        self,
        fund_id,
        fund_code: str = "",
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> FundNavListData:
        if self._nav_repo is None:
            return FundNavListData(items=[])
        navs = await self._nav_repo.get_by_fund_and_date_range(
            fund_id, start_date, end_date,
        )
        if navs:
            return FundNavListData(
                items=[FundNavResponse.model_validate(n) for n in navs],
            )

        # DB 无数据，从 AkShare 按需获取
        if self._fund_ds is not None and fund_code:
            raw = await self._fund_ds.fetch_fund_nav(fund_code, start_date=start_date)
            if raw:
                records = []
                for row in raw:
                    nav_date_val = row.get("date")
                    if nav_date_val is None:
                        continue
                    records.append({
                        "fund_id": fund_id,
                        "date": nav_date_val,
                        "nav": row.get("nav"),
                        "daily_change_pct": row.get("daily_change_pct"),
                    })
                if records:
                    await self._nav_repo.batch_upsert_nav(records)
                    await self._nav_repo.session.commit()
                    navs = await self._nav_repo.get_by_fund_and_date_range(
                        fund_id, start_date, end_date,
                    )
                    return FundNavListData(
                        items=[FundNavResponse.model_validate(n) for n in navs],
                    )

        return FundNavListData(items=[])

    async def collect_nav_all(self, code: str, start_date: str | None = None) -> dict:
        """获取基金全部历史净值和日涨跌幅。"""
        fund = await self._fund_repo.get_by_code(code)
        if fund is None:
            raise ValueError(f"基金 {code} 不存在")
        if self._fund_ds is None:
            raise RuntimeError("数据源未配置")
        raw = await self._fund_ds.fetch_fund_nav(code, start_date=start_date)
        return await self._save_nav_records(fund.id, raw)

    async def collect_nav_incremental(self, code: str) -> dict:
        """获取基金最新净值（从数据库中最新日期往后，包含当天）。"""
        fund = await self._fund_repo.get_by_code(code)
        if fund is None:
            raise ValueError(f"基金 {code} 不存在")
        if self._fund_ds is None:
            raise RuntimeError("数据源未配置")
        latest = await self._nav_repo.get_latest_nav_by_fund(fund.id)
        start_date = None if latest is None else latest.date
        raw = await self._fund_ds.fetch_fund_nav(code, start_date=start_date)
        return await self._save_nav_records(fund.id, raw)

    async def _save_nav_records(self, fund_id, raw) -> dict:
        """解析并持久化 NAV 数据."""
        if not raw:
            return {"added": 0, "updated": 0, "total": 0}
        records = []
        for row in raw:
            nav_date = row.get("date")
            if nav_date is None:
                continue
            records.append({
                "fund_id": fund_id,
                "date": nav_date,
                "nav": row.get("nav"),
                "daily_change_pct": row.get("daily_change_pct"),
            })
        if not records:
            return {"added": 0, "updated": 0, "total": 0}
        added, updated = await self._nav_repo.batch_upsert_nav(records)
        await self._nav_repo.session.commit()
        return {"added": added, "updated": updated, "total": added + updated}

    @staticmethod
    def _safe_float(value: object) -> float | None:
        """安全转换为 float，处理 AkShare 字符串格式（% 后缀、--- 占位等）."""
        if value is None:
            return None
        s = str(value).strip()
        if not s or s in ("---", "--", "—", "..."):
            return None
        # 去掉百分号
        if s.endswith("%"):
            s = s[:-1]
        try:
            f = float(s.replace(",", ""))
            if f != f:  # NaN check
                return None
            return f
        except (ValueError, TypeError):
            return None

    async def get_fund_estimate(
        self, fund_code: str,
    ) -> dict | None:
        """获取基金实时估值。

        优先从 fund_estimates 表读取缓存的最新记录，
        无数据时实时调 AkShare 获取（并回退到 latest_price / latest_nav）。
        """
        now = datetime.now(timezone.utc).isoformat()

        # 1. 优先读 DB 缓存
        if self._estimate_repo is not None:
            fund = await self._fund_repo.get_by_code(fund_code)
            if fund is not None:
                cached = await self._estimate_repo.get_by_fund(fund.id)
                if cached is not None and cached.estimate_nav is not None:
                    return {
                        "estimate_nav": float(cached.estimate_nav),
                        "estimate_change_pct": float(cached.estimate_change_pct) if cached.estimate_change_pct is not None else None,
                        "nav": None,
                        "daily_change_pct": None,
                        "timestamp": now,
                    }

        # 2. 回退：实时调 AkShare
        if self._fund_ds is None:
            return None
        raw = await self._fund_ds.fetch_estimate_by_code(fund_code)
        if raw and raw.get("estimate_nav") is not None:
            return {
                "estimate_nav": self._safe_float(raw.get("estimate_nav")),
                "estimate_change_pct": self._safe_float(raw.get("estimate_change_pct")),
                "nav": self._safe_float(raw.get("nav")),
                "daily_change_pct": self._safe_float(raw.get("daily_change_pct")),
                "timestamp": now,
            }

        # 回退 1：使用 latest_price / latest_change_pct (ETF)
        if fund is not None and fund.latest_price is not None:
            return {
                "estimate_nav": fund.latest_price,
                "estimate_change_pct": fund.latest_change_pct,
                "nav": fund.latest_price,
                "daily_change_pct": fund.latest_change_pct,
                "timestamp": now,
            }

        # 回退 2：使用数据库中的最新净值
        if fund is not None and self._nav_repo is not None:
            latest = await self._nav_repo.get_latest_nav_by_fund(fund.id)
            if latest is not None and latest.nav is not None:
                return {
                    "estimate_nav": None,
                    "estimate_change_pct": None,
                    "nav": float(latest.nav),
                    "daily_change_pct": float(latest.daily_change_pct) if latest.daily_change_pct is not None else None,
                    "timestamp": now,
                }
        return None

    async def get_batch_estimates(
        self, codes: list[str],
    ) -> list[dict]:
        """批量获取基金实时估值。

        优先从 fund_estimates 表读取缓存，缺失的走 AkShare 实时接口，
        再回退到 latest_price / latest_nav。
        """
        if not codes:
            return []
        now = datetime.now(timezone.utc).isoformat()
        result: list[dict] = []
        found: set[str] = set()

        # 1. 优先读 DB 缓存
        if self._estimate_repo is not None:
            funds = await self._fund_repo.get_by_codes(codes)
            for fund in funds:
                cached = await self._estimate_repo.get_by_fund(fund.id)
                if cached is not None and cached.estimate_nav is not None:
                    found.add(fund.code)
                    result.append({
                        "fund_code": fund.code,
                        "estimate_nav": float(cached.estimate_nav),
                        "estimate_change_pct": float(cached.estimate_change_pct) if cached.estimate_change_pct is not None else None,
                        "nav": None,
                        "daily_change_pct": None,
                        "timestamp": now,
                    })

        # 2. 回退：实时调 AkShare 补缺失
        missing = [c for c in codes if c not in found]
        if missing and self._fund_ds is not None:
            all_raw = await self._fund_ds.fetch_estimate_all()
            code_set = set(missing)

            for raw in all_raw:
                fc = str(raw.get("fund_code", ""))
                if fc in code_set and raw.get("estimate_nav") is not None:
                    found.add(fc)
                    result.append({
                        "fund_code": fc,
                        "estimate_nav": self._safe_float(raw.get("estimate_nav")),
                        "estimate_change_pct": self._safe_float(raw.get("estimate_change_pct")),
                        "nav": self._safe_float(raw.get("nav")),
                        "daily_change_pct": self._safe_float(raw.get("daily_change_pct")),
                        "timestamp": now,
                    })

            # ETF 回退
            still_missing = code_set - found
            if still_missing:
                funds = await self._fund_repo.get_by_codes(list(still_missing))
                for fund in funds:
                    if fund.latest_price is not None or fund.latest_change_pct is not None:
                        result.append({
                            "fund_code": fund.code,
                            "estimate_nav": self._safe_float(fund.latest_price),
                            "estimate_change_pct": self._safe_float(fund.latest_change_pct),
                            "nav": self._safe_float(fund.latest_price),
                            "daily_change_pct": self._safe_float(fund.latest_change_pct),
                            "timestamp": now,
                        })

        return result
