from abc import ABC, abstractmethod
from typing import Generic, List, Optional, Type, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar("T")


class IBaseRepository(ABC, Generic[T]):
    @abstractmethod
    async def find_by_id(self, entity_id: str) -> Optional[T]:
        pass

    @abstractmethod
    async def find_all(self) -> List[T]:
        pass

    @abstractmethod
    async def delete_by_id(self, entity_id: str) -> None:
        pass

    @abstractmethod
    async def create_entity(self, entity: T) -> T:
        pass


class BaseRepository(Generic[T], IBaseRepository[T]):
    def __init__(self, db_session: AsyncSession, model_cls: Type[T]):
        self._session = db_session
        self.model_cls = model_cls

    async def find_by_id(self, entity_id: str) -> Optional[T]:
        return await self._session.get(self.model_cls, entity_id)

    async def find_all(self) -> List[T]:
        result = await self._session.execute(select(self.model_cls))
        return list(result.scalars().all())

    async def delete_by_id(self, entity_id: str) -> None:
        entity = await self.find_by_id(entity_id)
        if entity:
            await self._session.delete(entity)

    async def create_entity(self, entity: T) -> T:
        self._session.add(entity)
        await self._session.flush()
        return entity
