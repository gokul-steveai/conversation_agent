from abc import ABC, abstractmethod
from typing import Generic, List, Optional, TypeVar

T = TypeVar("T")


class IBaseRepository(ABC, Generic[T]):
    """Abstract base repository contract for async database operations."""

    @classmethod
    @abstractmethod
    async def find_by_id(cls, entity_id: str) -> Optional[T]:
        pass

    @classmethod
    @abstractmethod
    async def find_all(cls) -> List[T]:
        pass

    @classmethod
    @abstractmethod
    async def delete_by_id(cls, entity_id: str) -> None:
        pass

    @classmethod
    @abstractmethod
    async def create_entity(cls, entity: T) -> None:
        pass
