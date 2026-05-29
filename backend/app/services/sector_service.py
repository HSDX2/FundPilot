"""Sector business logic — data transformation and orchestration."""

import uuid
from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.akshare.sector_datasource import SectorDataSource
from app.models.sector import SectorSnapshot
from app.repositories.sector_repo import (
    SectorMoneyFlowRepo,
    SectorRealtimeRepo,
    SectorRepo,
    SectorSnapshotRepo,
)
from app.schemas.sector import (
    SectorListData,
    SectorMoneyFlowRankItem,
    SectorMoneyFlowRankListData,
    SectorRankItem,
    SectorRankListData,
    SectorResponse,
    SectorSnapshotListData,
    SectorSnapshotResponse,
)


class SectorService:
    """Sector-related business logic."""

    def __init__(
        self,
        sector_repo: SectorRepo,
        sector_snapshot_repo: SectorSnapshotRepo | None = None,
        sector_money_flow_repo: SectorMoneyFlowRepo | None = None,
        sector_realtime_repo: SectorRealtimeRepo | None = None,
        sector_datasource: SectorDataSource | None = None,
    ):
        self._sector_repo = sector_repo
        self._snapshot_repo = sector_snapshot_repo
        self._money_flow_repo = sector_money_flow_repo
        self._realtime_repo = sector_realtime_repo
        self._sector_ds = sector_datasource or SectorDataSource()

    async def search_sectors(
        self,
        name: str | None = None,
        category: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> SectorListData:
        items, total = await self._sector_repo.search(
            name=name,
            category=category,
            page=page,
            page_size=page_size,
        )
        return SectorListData(
            items=[SectorResponse.model_validate(s) for s in items],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def get_sector_by_id(self, sector_id: uuid.UUID) -> SectorResponse | None:
        sector = await self._sector_repo.get(sector_id)
        if sector is None:
            return None
        return SectorResponse.model_validate(sector)

    async def get_sector_snapshots(
        self,
        sector_id: uuid.UUID,
        start_time: date | None = None,
        end_time: date | None = None,
    ) -> SectorSnapshotListData:
        if self._snapshot_repo is None:
            return SectorSnapshotListData(items=[])
        snapshots = await self._snapshot_repo.get_by_sector_and_time_range(
            sector_id, start_time, end_time,
        )
        return SectorSnapshotListData(
            items=[SectorSnapshotResponse.model_validate(s) for s in snapshots],
        )

    async def get_sector_realtime(
        self,
        sector_id: uuid.UUID,
    ) -> dict | None:
        """获取板块实时行情，返回数据库快照 + THS 实时估算数据。"""
        sector = await self._sector_repo.get(sector_id)
        if sector is None:
            return None

        # 1. THS 实时数据
        rt = None
        if self._sector_ds:
            try:
                rt = await self._sector_ds.fetch_sector_realtime(
                    name=sector.name, category=sector.category or "industry",
                )
            except Exception:
                import logging
                logger = logging.getLogger(__name__)
                logger.exception("获取板块实时行情失败: %s", sector.name)

        # 2. 数据库最新收盘快照
        snapshot = None
        if self._snapshot_repo:
            snapshot = await self._snapshot_repo.get_latest_by_sector(sector_id)

        if snapshot is None and rt is None:
            return None

        # 3. 构建基础数据（DB 快照）
        result = {}
        if snapshot:
            result = SectorSnapshotResponse.model_validate(snapshot).model_dump()

        # 4. 实时估算数据
        if rt:
            try:
                rt_change_pct = float(rt.get("change_pct"))
            except (ValueError, TypeError):
                rt_change_pct = None

            latest_close = (
                float(snapshot.price)
                if snapshot is not None and snapshot.price is not None
                else None
            )
            rt_price = (
                round(latest_close * (1 + rt_change_pct / 100), 4)
                if latest_close is not None and rt_change_pct is not None
                else None
            )

            result["realtime"] = {
                "price": rt_price,
                "change_pct": rt_change_pct,
            }
        else:
            result["realtime"] = None

        return result

    async def get_rank(
        self,
        session: AsyncSession,
        category: str | None = None,
        limit: int = 20,
        sort_by: str = "change_pct",
        watched_ids: set[uuid.UUID] | None = None,
    ) -> SectorRankListData:
        if self._snapshot_repo is None:
            return SectorRankListData(items=[])

        # 获取所有板块（含无数据板块），LEFT JOIN 最新快照
        if category:
            sectors = await self._sector_repo.get_active_by_category(category)
        else:
            sectors = await self._sector_repo.get_all_active()

        if not sectors:
            return SectorRankListData(items=[])

        if watched_ids is not None:
            sectors = [s for s in sectors if s.id in watched_ids]

        sector_ids = [s.id for s in sectors]
        snapshots = await self._snapshot_repo.get_latest_per_sector(sector_ids)
        snapshot_map = {s.sector_id: s for s in snapshots}

        # 实时行情（批量查询，避免 N+1）
        rt_map: dict[uuid.UUID, dict] = {}
        if self._realtime_repo is not None:
            from app.repositories.sector_repo import SectorRealtimeRepo
            industry_ids = [s.id for s in sectors if s.category == "industry"]
            if industry_ids:
                rt_records = await self._realtime_repo.get_by_sectors(industry_ids)
                for sid, rt in rt_records.items():
                    rt_map[sid] = {
                        "price": rt.price,
                        "change_pct": rt.change_pct,
                        "volume": rt.volume,
                        "turnover": rt.turnover,
                    }

        items = []
        for sector in sectors:
            snap = snapshot_map.get(sector.id)
            rt = rt_map.get(sector.id)
            price = str(snap.price) if snap and snap.price is not None else None
            change_pct = str(snap.change_pct) if snap and snap.change_pct is not None else None
            rt_price = str(rt["price"]) if rt and rt["price"] is not None else None
            rt_change_pct = str(rt["change_pct"]) if rt and rt["change_pct"] is not None else None
            items.append(
                SectorRankItem(
                    sector_id=sector.id,
                    sector_name=sector.name,
                    category=sector.category,
                    price=price,
                    change_pct=change_pct,
                    realtime_price=rt_price,
                    realtime_change_pct=rt_change_pct,
                    timestamp=snap.timestamp if snap else None,
                )
            )

        # 按指定字段降序排列，无数据排在最后
        if sort_by == "realtime_change_pct":
            items.sort(key=lambda x: (
                0 if x.realtime_change_pct is not None else 1,
                -(float(x.realtime_change_pct) if x.realtime_change_pct is not None
                  else float(x.change_pct) if x.change_pct is not None else 0),
            ))
        else:
            items.sort(key=lambda x: (
                0 if x.change_pct is not None else 1,
                -(float(x.change_pct) if x.change_pct is not None else 0),
            ))
        items = items[:limit]

        return SectorRankListData(items=items, total=len(items))

    async def get_money_flow_rank(
        self,
        period: str = "today",
        sector_type: str | None = None,
    ) -> SectorMoneyFlowRankListData:
        """从 THS 获取板块资金流向排行。

        Args:
            period: today / 3d / 5d / 10d
            sector_type: industry / concept，None=全部
        """
        indicator_map = {"today": "今日", "3d": "3日", "5d": "5日", "10d": "10日"}
        indicator = indicator_map.get(period, "今日")

        all_items: list[dict] = []
        if sector_type is None or sector_type == "industry":
            items = await self._sector_ds.fetch_sector_fund_flow(
                indicator, "行业资金流",
            )
            for item in items:
                item["category"] = "industry"
            all_items.extend(items)
        if sector_type is None or sector_type == "concept":
            items = await self._sector_ds.fetch_sector_fund_flow(
                indicator, "概念资金流",
            )
            for item in items:
                item["category"] = "concept"
            all_items.extend(items)

        # 按净流入降序排列
        all_items.sort(key=lambda x: -(x.get("main_force_net_inflow") or 0))

        # 为每个条目查找 DB 中的 sector_id（用于前端跳转）
        sectors = await self._sector_repo.get_all_active()
        name_to_id: dict[str, str] = {}
        for s in sectors:
            key = f"{s.name}|{s.category}"
            name_to_id[key] = str(s.id)

        for item in all_items:
            key = f"{item.get('name')}|{item.get('category')}"
            item["id"] = name_to_id.get(key)

        return SectorMoneyFlowRankListData(
            items=[SectorMoneyFlowRankItem.model_validate(item) for item in all_items],
        )

    # ── Data Collection ────────────────────────────────────────────────

    async def collect_data_all(self, sector_id: uuid.UUID, start_date: str | None = None) -> dict:
        """获取板块全部历史资金流向、净值和涨跌幅。"""
        sector = await self._sector_repo.get(sector_id)
        if sector is None:
            raise ValueError(f"板块 {sector_id} 不存在")
        sd = date.fromisoformat(start_date) if start_date else None
        return await self._collect_sector_data(sector, start_date=sd)

    async def collect_data_incremental(
        self, sector_id: uuid.UUID, backfill_mf_detail: bool = True,
    ) -> dict:
        """获取板块最新数据（从数据库中最新日期往后，包含当天）。"""
        sector = await self._sector_repo.get(sector_id)
        if sector is None:
            raise ValueError(f"板块 {sector_id} 不存在")

        latest = None
        if self._snapshot_repo:
            snap = await self._snapshot_repo.get_latest_by_sector(sector_id)
            if snap and snap.timestamp:
                snap_date = snap.timestamp
                latest = max(latest, snap_date) if latest else snap_date
        if self._money_flow_repo:
            from sqlalchemy import select as sa_select
            from app.models.sector import SectorMoneyFlow
            stmt = (
                sa_select(SectorMoneyFlow.date)
                .where(SectorMoneyFlow.sector_id == sector_id)
                .order_by(SectorMoneyFlow.date.desc())
                .limit(1)
            )
            result = await self._sector_repo.session.execute(stmt)
            row = result.scalar_one_or_none()
            if row:
                latest = max(latest, row) if latest else row

        # 资金流向起始日期取中单/散户有值的最新日期，
        # 确保已有数据中缺少细分（如 THS 采集的仅总额记录）也能回补
        mf_start: date | None = None
        if self._money_flow_repo:
            mf_start = await self._money_flow_repo.get_latest_complete_date(sector_id)

        start_date = None if latest is None else latest
        return await self._collect_sector_data(
            sector, start_date=start_date,
            mf_start_date=mf_start,
            backfill_mf_detail=backfill_mf_detail,
        )

    async def _collect_sector_data(
        self, sector, start_date: date | None,
        mf_start_date: date | None = None,
        backfill_mf_detail: bool = True,
    ) -> dict:
        """内部方法：获取并持久化板块的行情快照和资金流向。"""
        added = 0
        updated = 0

        # 1. 收集历史行情快照（OHLC + 涨跌幅）
        if self._snapshot_repo and self._sector_ds:
            try:
                sd = start_date.isoformat() if start_date else None
                now = date.today().isoformat()
                history = await self._sector_ds.fetch_board_history(
                    name=sector.name,
                    category=sector.category or "industry",
                    start_date=sd,
                    end_date=now,
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
                        # 跳过非交易日（周末）
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
                            "change_pct": None,  # 从连续收盘价计算
                            "volume": row.get("volume"),
                            "turnover": row.get("turnover"),
                        })
                    # 按时间排序后计算涨跌幅
                    records.sort(key=lambda r: r["timestamp"])
                    for i in range(len(records)):
                        if i > 0 and records[i - 1].get("price") and records[i].get("price"):
                            prev = float(records[i - 1]["price"])
                            curr = float(records[i]["price"])
                            if prev != 0:
                                records[i]["change_pct"] = round(
                                    (curr - prev) / prev * 100, 4,
                                )
                    # 补算第一条记录：如果本批最早记录之前已有数据，从数据库取前日收盘价
                    if records and records[0].get("change_pct") is None and records[0].get("price") is not None:
                        try:
                            prev_snap = await self._snapshot_repo.get_latest_before_date(
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
                    a, u = await self._snapshot_repo.batch_upsert_snapshots(records)
                    added += a
                    updated += u
            except Exception:
                import logging
                logger = logging.getLogger(__name__)
                logger.exception("收集板块行情快照失败: %s", sector.name)

        # 2. 收集资金流向
        if self._money_flow_repo and self._sector_ds:
            try:
                if backfill_mf_detail:
                    # 正常路径：EM push2his（含中单/散户三分类），可能被 WAF 拦截
                    mf_start = mf_start_date if mf_start_date else (start_date if start_date else date(2000, 1, 1))
                    flows = await self._sector_ds.fetch_sector_fund_flow_range(
                        symbol=sector.name,
                        start_date=mf_start,
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
                        a, u = await self._money_flow_repo.batch_upsert(records)
                        added += a
                        updated += u
                else:
                    # THS-only 路径：跳过 EM push2his（避免 WAF 拦截问题），仅获取 THS 总额数据
                    # 15:00（北京时间）前当日交易未结束，算昨日数据
                    from datetime import datetime, timezone, timedelta
                    beijing_hour = datetime.now(timezone(timedelta(hours=8))).hour
                    mf_effective_date = date.today()
                    if beijing_hour < 15:
                        mf_effective_date = mf_effective_date - timedelta(days=1)

                    ths_data = await self._sector_ds._fetch_thz_fund_flow_today(sector.name)
                    if ths_data:
                        records = [{
                            "sector_id": sector.id,
                            "date": mf_effective_date,
                            "main_force_net_inflow": ths_data[0].get("main_force_net_inflow"),
                            "retail_net_inflow": None,
                            "middle_net_inflow": None,
                        }]
                        a, u = await self._money_flow_repo.batch_upsert(records)
                        added += a
                        updated += u
            except Exception:
                import logging
                logger = logging.getLogger(__name__)
                logger.exception("收集板块资金流向失败: %s", sector.name)

        await self._sector_repo.session.commit()
        return {"added": added, "updated": updated, "total": added + updated}
