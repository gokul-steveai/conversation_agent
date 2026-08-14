from typing import AsyncGenerator

from controllers.chat_controller import ChatController
from core.database import DatabaseManager
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from repositories import (
    MemoryRepository,
    SessionRepository,
    UserRepository,
    VectorStoreRepository,
)
from schemas import UserResponse
from services import AuthService, MemoryService, SessionService
from sqlalchemy.ext.asyncio import AsyncSession

http_bearer_scheme = HTTPBearer(auto_error=False)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with DatabaseManager.get_db() as session:
        yield session


def get_user_repository(
    db: AsyncSession = Depends(get_db_session),
) -> UserRepository:
    return UserRepository(db)


def get_session_repository(
    db: AsyncSession = Depends(get_db_session),
) -> SessionRepository:
    return SessionRepository(db)


def get_memory_repository(
    db: AsyncSession = Depends(get_db_session),
) -> MemoryRepository:
    return MemoryRepository(db)


def get_vector_store_repository(
    db: AsyncSession = Depends(get_db_session),
) -> VectorStoreRepository:
    return VectorStoreRepository(db)


def get_auth_service(
    user_repo: UserRepository = Depends(get_user_repository),
) -> AuthService:
    return AuthService(user_repo=user_repo)


def get_session_service(
    session_repo: SessionRepository = Depends(get_session_repository),
    user_repo: UserRepository = Depends(get_user_repository),
) -> SessionService:
    return SessionService(session_repo=session_repo, user_repo=user_repo)


def get_memory_service(
    memory_repo: MemoryRepository = Depends(get_memory_repository),
    vector_repo: VectorStoreRepository = Depends(get_vector_store_repository),
    session_service: SessionService = Depends(get_session_service),
) -> MemoryService:
    return MemoryService(
        memory_repository=memory_repo,
        vector_repository=vector_repo,
        session_service=session_service,
    )


def get_chat_controller(
    memory_service: MemoryService = Depends(get_memory_service),
) -> ChatController:
    return ChatController(memory_service=memory_service)


async def get_current_user_optional(
    authorization_credentials: HTTPAuthorizationCredentials = Depends(
        http_bearer_scheme
    ),
) -> UserResponse | None:
    if not authorization_credentials or not authorization_credentials.credentials:
        return None
    token_payload = AuthService.verify_access_token(
        authorization_credentials.credentials
    )
    if not token_payload:
        return None
    return UserResponse(
        user_id=token_payload.get("sub", ""),
        name=token_payload.get("name", ""),
        email=token_payload.get("email", ""),
    )


async def get_current_user(
    user: UserResponse | None = Depends(get_current_user_optional),
) -> UserResponse:
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing, invalid, or expired authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user
