from typing import AsyncContextManager, Callable, List, Optional, Type

from core import get_db
from models.memory import BaseVectorModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class VectorStoreRepository:
    def __init__(
        self,
        session_factory: Optional[
            Callable[[], AsyncContextManager[AsyncSession]]
        ] = None,
    ) -> None:
        self.session_factory = session_factory or get_db

    async def add_vector_records(self, records: List[BaseVectorModel]) -> List[str]:
        record_ids: List[str] = []
        async with self.session_factory() as session:
            for record in records:
                session.add(record)
                record_ids.append(record.id)
            await session.commit()
        return record_ids

    async def get_all_vector_records(
        self, model_cls: Type[BaseVectorModel]
    ) -> List[BaseVectorModel]:
        async with self.session_factory() as session:
            stmt = select(model_cls)
            result = await session.execute(stmt)
            return list(result.scalars().all())
