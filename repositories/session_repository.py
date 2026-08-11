import asyncio
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator, List, Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from config.settings import settings
from models.db_models import Base, SessionModel
from repositories.base_repository import IBaseRepository
from utils.logger import logger


class SessionRepository(IBaseRepository[SessionModel]):
    """Async Production-grade Repository Pattern implementation for conversation session database operations."""

    _engine = None
    _SessionLocal = None
    _engine_loop = None

    @classmethod
    def _get_async_url(cls, raw_url: str) -> str:
        if raw_url.startswith("postgresql://"):
            return raw_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        elif raw_url.startswith("sqlite:///"):
            return raw_url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
        elif not raw_url.startswith("sqlite+aiosqlite") and not raw_url.startswith(
            "postgresql+asyncpg"
        ):
            return "sqlite+aiosqlite:///data/conversations.db"
        return raw_url

    @classmethod
    async def _init_engine(cls) -> None:
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            current_loop = None

        if cls._engine is not None and cls._engine_loop != current_loop:
            cls._engine = None

        if cls._engine is not None:
            return

        cls._engine_loop = current_loop
        db_url = cls._get_async_url(settings.database_url)
        os.makedirs("data", exist_ok=True)

        try:
            if "postgresql" in db_url:
                cls._engine = create_async_engine(
                    db_url,
                    poolclass=NullPool,
                )
            else:
                cls._engine = create_async_engine(
                    db_url,
                    poolclass=NullPool,
                )

            async with cls._engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

            cls._SessionLocal = async_sessionmaker(
                bind=cls._engine, expire_on_commit=False, class_=AsyncSession
            )
        except Exception as e:
            logger.warning(
                f"Failed to connect to primary async database ({e}). Falling back to Async SQLite."
            )
            cls._engine = create_async_engine(
                "sqlite+aiosqlite:///data/conversations.db",
                poolclass=NullPool,
            )
            async with cls._engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            cls._SessionLocal = async_sessionmaker(
                bind=cls._engine, expire_on_commit=False, class_=AsyncSession
            )

    @classmethod
    @asynccontextmanager
    async def get_db(cls) -> AsyncGenerator[AsyncSession, None]:
        """Provides an async transactional context manager for database sessions."""
        await cls._init_engine()
        async with cls._SessionLocal() as db:
            try:
                yield db
                await db.commit()
            except Exception as e:
                await db.rollback()
                logger.error(f"Async database transaction error: {e}")
                raise

    @classmethod
    async def save_entity(
        cls,
        session_id: str,
        title: str,
        state_json: str,
        messages_json: str,
        history_json: str,
        created_at: str,
        updated_at: str,
    ) -> None:
        async with cls.get_db() as db:
            result = await db.execute(
                select(SessionModel).filter(SessionModel.session_id == session_id)
            )
            existing = result.scalars().first()

            if existing:
                existing.title = title
                existing.state_json = state_json
                existing.messages_json = messages_json
                existing.history_json = history_json
                existing.updated_at = updated_at
            else:
                new_sess = SessionModel(
                    session_id=session_id,
                    title=title,
                    state_json=state_json,
                    messages_json=messages_json,
                    history_json=history_json,
                    created_at=created_at,
                    updated_at=updated_at,
                )
                db.add(new_sess)

    @classmethod
    async def find_by_id(cls, session_id: str) -> Optional[SessionModel]:
        await cls._init_engine()
        async with cls._SessionLocal() as db:
            result = await db.execute(
                select(SessionModel).filter(SessionModel.session_id == session_id)
            )
            return result.scalars().first()

    @classmethod
    async def find_all(cls) -> List[SessionModel]:
        await cls._init_engine()
        async with cls._SessionLocal() as db:
            result = await db.execute(
                select(SessionModel).order_by(SessionModel.updated_at.desc())
            )
            return list(result.scalars().all())

    @classmethod
    async def delete_by_id(cls, session_id: str) -> None:
        async with cls.get_db() as db:
            await db.execute(
                delete(SessionModel).filter(SessionModel.session_id == session_id)
            )
