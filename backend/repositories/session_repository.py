from datetime import datetime, timezone
from typing import List, Optional

from models import SessionModel
from repositories.base_repository import BaseRepository
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession
from utils import logger


class SessionRepository(BaseRepository[SessionModel]):
    def __init__(self, db_session: AsyncSession):
        super().__init__(db_session=db_session, model_cls=SessionModel)

    async def save_entity(
        self,
        session_id: str,
        user_id: str,
        title: str,
        state_json: str,
        messages_json: str,
        history_json: str,
    ) -> None:
        bind = self._session.bind
        dialect_name = bind.dialect.name if bind else ""

        insert_fn = pg_insert if "postgresql" in dialect_name else sqlite_insert

        insert_stmt = insert_fn(SessionModel).values(
            session_id=session_id,
            user_id=user_id,
            title=title,
            state_json=state_json,
            messages_json=messages_json,
            history_json=history_json,
            is_active=True,
        )

        upsert_stmt = insert_stmt.on_conflict_do_update(
            index_elements=[SessionModel.session_id],
            set_={
                "user_id": user_id,
                "title": title,
                "state_json": state_json,
                "messages_json": messages_json,
                "history_json": history_json,
                "updated_at": datetime.now(timezone.utc),
                "is_active": True,
            },
        )

        await self._session.execute(upsert_stmt)

    async def find_by_session_and_user_id(
        self, session_id: str, user_id: str
    ) -> Optional[SessionModel]:
        result = await self._session.execute(
            select(SessionModel).filter(
                SessionModel.session_id == session_id,
                SessionModel.user_id == user_id,
                SessionModel.is_active == True,  # noqa: E712
            )
        )
        return result.scalars().first()

    async def find_all_by_user(self, user_id: str) -> List[SessionModel]:
        result = await self._session.execute(
            select(SessionModel)
            .filter(
                SessionModel.user_id == user_id,
                SessionModel.is_active == True,  # noqa: E712
            )
            .order_by(SessionModel.updated_at.desc())
        )
        return list(result.scalars().all())

    async def find_all(self) -> List[SessionModel]:
        result = await self._session.execute(
            select(SessionModel)
            .filter(SessionModel.is_active == True)  # noqa: E712
            .order_by(SessionModel.updated_at.desc())
        )
        return list(result.scalars().all())

    async def delete_by_session_id_and_user_id(
        self, session_id: str, user_id: str = ""
    ) -> None:
        stmt = select(SessionModel).filter(SessionModel.session_id == session_id)
        if user_id:
            stmt = stmt.filter(SessionModel.user_id == user_id)
        result = await self._session.execute(stmt)
        session = result.scalars().first()
        if session:
            session.is_active = False
        else:
            logger.warning(f"Session with ID {session_id} not found for deletion.")
