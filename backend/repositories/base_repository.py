from abc import ABC, abstractmethod
from typing import Generic, List, Optional, TypeVar

T = TypeVar("T")


class IBaseRepository(ABC, Generic[T]):
    """Abstract base repository contract for async database operations."""

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
    async def create_entity(self, entity: T) -> None:
        pass
