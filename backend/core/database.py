import asyncio
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from config.settings import settings
from models import Base
from sqlalchemy import AsyncAdaptedQueuePool
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from utils.logger import logger


class DatabaseManager:
    _engine = None
    _SessionLocal = None
    _engine_loop = None
    _init_lock: Optional[asyncio.Lock] = None
    _init_lock_guard: Optional[asyncio.Lock] = None

    @classmethod
    async def _get_init_lock(cls) -> asyncio.Lock:
        if cls._init_lock_guard is None:
            cls._init_lock_guard = asyncio.Lock()
        async with cls._init_lock_guard:
            if cls._init_lock is None:
                cls._init_lock = asyncio.Lock()
            return cls._init_lock

    @classmethod
    def get_async_url(cls, raw_url: str) -> str:
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
    async def init_engine(cls) -> None:
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            current_loop = None

        if (
            cls._engine is not None
            and cls._SessionLocal is not None
            and cls._engine_loop == current_loop
        ):
            return

        init_lock = await cls._get_init_lock()
        async with init_lock:
            if (
                cls._engine is not None
                and cls._SessionLocal is not None
                and cls._engine_loop == current_loop
            ):
                return

            if cls._engine is not None and cls._engine_loop != current_loop:
                try:
                    await cls._engine.dispose()
                except Exception:
                    pass
                cls._engine = None
                cls._SessionLocal = None

            cls._engine_loop = current_loop
            db_url = cls.get_async_url(settings.database_url)
            os.makedirs("data", exist_ok=True)

            try:
                if "postgresql" in db_url:
                    engine = create_async_engine(
                        db_url,
                        poolclass=AsyncAdaptedQueuePool,
                        pool_size=10,
                        max_overflow=20,
                        pool_timeout=30,
                        pool_pre_ping=True,
                        pool_recycle=1800,
                    )
                else:
                    engine = create_async_engine(
                        db_url,
                        poolclass=NullPool,
                    )

                async with engine.begin() as conn:
                    await conn.run_sync(Base.metadata.create_all)

                session_factory = async_sessionmaker(
                    bind=engine, expire_on_commit=False, class_=AsyncSession
                )

                # Atomically publish engine and session_factory ONLY AFTER schema creation succeeds
                cls._engine = engine
                cls._SessionLocal = session_factory
            except Exception as e:
                cls._engine = None
                cls._SessionLocal = None
                cls._engine_loop = None
                logger.error(
                    f"Database engine initialization failed for URL '{db_url.split('@')[-1]}': {e}"
                )
                raise

    @classmethod
    async def close_engine(cls) -> None:
        if cls._engine is not None:
            try:
                await cls._engine.dispose()
            except Exception as e:
                logger.error(f"Error disposing database engine: {e}")
            cls._engine = None
            cls._SessionLocal = None
            cls._engine_loop = None

    @classmethod
    @asynccontextmanager
    async def get_db(cls) -> AsyncGenerator[AsyncSession, None]:
        await cls.init_engine()
        async with cls._SessionLocal() as db:
            try:
                yield db
                await db.commit()
            except Exception as e:
                await db.rollback()
                logger.error(f"Async database transaction error: {e}")
                raise


@asynccontextmanager
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with DatabaseManager.get_db() as session:
        yield session
