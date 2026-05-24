from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import Base


class BaseRepository[T: Base]:
    """Generic CRUD repository base class."""

    def __init__(self, session: AsyncSession, model: type[T]):
        self.session = session
        self.model = model

    async def get(self, id: UUID) -> T | None:
        """Get a record by UUID primary key."""
        return await self.session.get(self.model, id)

    async def list(
        self,
        skip: int = 0,
        limit: int = 20,
        **filters,
    ) -> list[T]:
        """List records with optional equality filters."""
        stmt = select(self.model)
        for key, value in filters.items():
            if value is not None:
                column = getattr(self.model, key, None)
                if column is not None:
                    stmt = stmt.where(column == value)
        stmt = stmt.offset(skip).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, obj: T) -> T:
        """Create a new record."""
        self.session.add(obj)
        await self.session.flush()
        return obj

    async def update(self, id: UUID, data: dict) -> T | None:
        """Update a record by UUID primary key. Returns None if not found."""
        obj = await self.get(id)
        if obj is None:
            return None
        for key, value in data.items():
            if hasattr(obj, key):
                setattr(obj, key, value)
        await self.session.flush()
        return obj

    async def delete(self, id: UUID) -> bool:
        """Delete a record by UUID primary key. Returns True if deleted."""
        obj = await self.get(id)
        if obj is None:
            return False
        await self.session.delete(obj)
        await self.session.flush()
        return True

    async def count(self, **filters) -> int:
        """Count records with optional equality filters."""
        stmt = select(func.count(self.model.id))
        for key, value in filters.items():
            if value is not None:
                column = getattr(self.model, key, None)
                if column is not None:
                    stmt = stmt.where(column == value)
        result = await self.session.execute(stmt)
        return result.scalar() or 0
