from typing import List, Type

from models.memory import BaseVectorModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class VectorStoreRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def add_vector_records(self, records: List[BaseVectorModel]) -> List[str]:
        record_ids: List[str] = []
        for record in records:
            self.db.add(record)
            record_ids.append(record.id)
        await self.db.flush()
        return record_ids

    async def get_all_vector_records(
        self, model_cls: Type[BaseVectorModel]
    ) -> List[BaseVectorModel]:
        stmt = select(model_cls)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_candidate_vector_records(
        self, model_cls: Type[BaseVectorModel], limit: int = 100
    ) -> List[BaseVectorModel]:
        stmt = select(model_cls).order_by(model_cls.created_at.desc()).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
