from datetime import datetime, timezone
from typing import List, Optional

from core import get_db
from models import SessionModel
from repositories import IBaseRepository
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from utils import logger


class SessionRepository(IBaseRepository[SessionModel]):
    @classmethod
    async def save_entity(
        cls,
        session_id: str,
        user_id: str,
        title: str,
        state_json: str,
        messages_json: str,
        history_json: str,
    ) -> None:
        async with get_db() as db:
            bind = db.bind
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

            await db.execute(upsert_stmt)

    @classmethod
    async def find_by_id(cls, session_id: str, user_id: str) -> Optional[SessionModel]:
        async with get_db() as db:
            result = await db.execute(
                select(SessionModel).filter(
                    SessionModel.session_id == session_id,
                    SessionModel.user_id == user_id,
                    SessionModel.is_active == True,  # noqa: E712
                )
            )
            return result.scalars().first()

    @classmethod
    async def find_all_by_user(cls, user_id: str) -> List[SessionModel]:
        async with get_db() as db:
            result = await db.execute(
                select(SessionModel)
                .filter(
                    SessionModel.user_id == user_id,
                    SessionModel.is_active == True,  # noqa: E712
                )
                .order_by(SessionModel.updated_at.desc())
            )
            return list(result.scalars().all())

    @classmethod
    async def find_all(cls) -> List[SessionModel]:
        async with get_db() as db:
            result = await db.execute(
                select(SessionModel)
                .filter(SessionModel.is_active == True)  # noqa: E712
                .order_by(SessionModel.updated_at.desc())
            )
            return list(result.scalars().all())

    @classmethod
    async def delete_by_id(cls, session_id: str, user_id: str = "") -> None:
        async with get_db() as db:
            stmt = select(SessionModel).filter(SessionModel.session_id == session_id)
            if user_id:
                stmt = stmt.filter(SessionModel.user_id == user_id)
            result = await db.execute(stmt)
            session = result.scalars().first()
            if session:
                session.is_active = False
            else:
                logger.warning(f"Session with ID {session_id} not found for deletion.")
