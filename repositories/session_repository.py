import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import DatabaseManager, get_db
from models.session import SessionModel
from repositories.base_repository import IBaseRepository
from utils.logger import logger


class SessionRepository(IBaseRepository[SessionModel]):
    """Async Production-grade Repository Pattern implementation for owner-scoped session database operations."""

    _save_locks: Dict[str, asyncio.Lock] = {}
    _locks_guard: Optional[asyncio.Lock] = None

    @classmethod
    async def _get_session_lock(cls, session_id: str) -> asyncio.Lock:
        if cls._locks_guard is None:
            cls._locks_guard = asyncio.Lock()
        async with cls._locks_guard:
            if session_id not in cls._save_locks:
                cls._save_locks[session_id] = asyncio.Lock()
            return cls._save_locks[session_id]

    @classmethod
    async def _init_engine(cls) -> None:
        """Legacy delegate method initializing central database engine."""
        await DatabaseManager.init_engine()

    @classmethod
    @asynccontextmanager
    async def get_db(cls) -> AsyncGenerator[AsyncSession, None]:
        """Legacy delegate providing centralized transactional context manager for database sessions."""
        async with get_db() as db:
            yield db

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
        """Atomic database-native upsert with per-session write serialization, preserving created_at timestamps."""
        session_lock = await cls._get_session_lock(session_id)
        async with session_lock:
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

                from datetime import datetime, timezone

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
        """Deprecated legacy call: returns all active sessions across system."""
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
