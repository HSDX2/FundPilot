from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.system import AIProvider, CollectLog, CollectorSetting, PromptSetting
from app.repositories.base import BaseRepository


class AIProviderRepo(BaseRepository[AIProvider]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, AIProvider)

    async def get_active(self) -> AIProvider | None:
        stmt = select(AIProvider).where(AIProvider.is_active.is_(True))
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def set_active(self, provider_id) -> AIProvider:
        """Deactivate all providers, then activate the specified one."""
        deactivate = (
            update(AIProvider)
            .where(AIProvider.is_active.is_(True))
            .values(is_active=False)
        )
        await self.session.execute(deactivate)
        activate = (
            update(AIProvider)
            .where(AIProvider.id == provider_id)
            .values(is_active=True)
        )
        await self.session.execute(activate)
        await self.session.flush()
        return await self.get(provider_id)

    async def list_by_types(
        self,
        provider_types: list[str] | None = None,
    ) -> list[AIProvider]:
        stmt = select(AIProvider)
        if provider_types:
            stmt = stmt.where(AIProvider.provider_type.in_(provider_types))
        stmt = stmt.order_by(AIProvider.name)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


class CollectorSettingRepo(BaseRepository[CollectorSetting]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, CollectorSetting)

    async def list(
        self,
        skip: int = 0,
        limit: int = 20,
        **filters,
    ) -> list[CollectorSetting]:
        """List collector settings ordered by sort_order."""
        stmt = select(CollectorSetting).order_by(CollectorSetting.sort_order)
        for key, value in filters.items():
            if value is not None:
                column = getattr(CollectorSetting, key, None)
                if column is not None:
                    stmt = stmt.where(column == value)
        if skip:
            stmt = stmt.offset(skip)
        if limit:
            stmt = stmt.limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_name(self, name: str) -> CollectorSetting | None:
        stmt = select(CollectorSetting).where(
            CollectorSetting.collector_name == name
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_last_run(
        self,
        name: str,
        status: str,
    ) -> None:
        """Update last_run_at and last_status for a collector."""
        stmt = (
            update(CollectorSetting)
            .where(CollectorSetting.collector_name == name)
            .values(
                last_run_at=datetime.now(),
                last_status=status,
            )
        )
        await self.session.execute(stmt)
        await self.session.flush()

    async def initialize_defaults(
        self,
        defaults: dict[str, dict],
    ) -> None:
        """插入不存在的采集器配置，已有数据的不做任何修改。"""
        for name, meta in defaults.items():
            existing = await self.get_by_name(name)
            if existing is not None:
                continue
            setting = CollectorSetting(
                collector_name=name,
                display_name=str(meta.get("display_name", name)),
                description=str(meta.get("description", "")),
                interval_seconds=int(meta.get("interval_seconds", 86400)),
                is_active=bool(meta.get("is_active", True)),
                sort_order=int(meta.get("sort_order", 0)),
                schedule_config=meta.get("schedule_config"),
                other_config=meta.get("other_config"),
            )
            self.session.add(setting)
        await self.session.flush()


class CollectLogRepo(BaseRepository[CollectLog]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, CollectLog)

    async def list_by_collector(
        self,
        collector_name: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[Sequence[CollectLog], int]:
        query = select(CollectLog)
        count_query = select(func.count(CollectLog.id))

        if collector_name:
            query = query.where(CollectLog.collector_name == collector_name)
            count_query = count_query.where(
                CollectLog.collector_name == collector_name
            )

        count_result = await self.session.execute(count_query)
        total = count_result.scalar() or 0

        query = query.order_by(CollectLog.started_at.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(query)
        items = result.scalars().all()

        return items, total

    async def delete_all(self) -> int:
        """Delete all collect log records. Returns count deleted."""
        from sqlalchemy import delete

        result = await self.session.execute(delete(CollectLog))
        await self.session.flush()
        return result.rowcount


class PromptSettingRepo(BaseRepository[PromptSetting]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, PromptSetting)

    async def get_by_key(self, key: str) -> PromptSetting | None:
        stmt = select(PromptSetting).where(PromptSetting.prompt_key == key)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def upsert(self, key: str, text: str) -> PromptSetting:
        """Create or update a prompt setting."""
        existing = await self.get_by_key(key)
        if existing:
            existing.prompt_text = text
        else:
            existing = PromptSetting(prompt_key=key, prompt_text=text)
            self.session.add(existing)
        await self.session.flush()
        return existing

    async def get_all(self) -> dict[str, str | None]:
        """Returns {prompt_key: prompt_text} for all stored prompts."""
        stmt = select(PromptSetting)
        result = await self.session.execute(stmt)
        return {r.prompt_key: r.prompt_text for r in result.scalars().all()}
