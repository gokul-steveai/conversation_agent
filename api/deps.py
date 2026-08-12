from typing import AsyncGenerator

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import DatabaseManager
from schemas.auth import UserResponse
from services.auth_service import AuthService

http_bearer_scheme = HTTPBearer(auto_error=False)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with DatabaseManager.get_db() as session:
        yield session


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
