from typing import List, Optional

from schemas import (
    CreateSessionRequest,
    SaveSessionRequest,
    SessionDetailResponse,
    SessionResponse,
)
from services.session_service import SessionService


class MemoryService:
    @classmethod
    async def create_session(
        cls, request: CreateSessionRequest
    ) -> SessionDetailResponse:
        return await SessionService.create_session(request)

    @classmethod
    async def save_session(
        cls,
        request: SaveSessionRequest,
    ) -> None:
        await SessionService.save_session(request)

    @classmethod
    async def load_session(
        cls, session_id: str, user_id: str
    ) -> Optional[SessionDetailResponse]:
        return await SessionService.load_session(session_id, user_id)

    @classmethod
    async def list_sessions(cls, user_id: str) -> List[SessionResponse]:
        return await SessionService.list_sessions(user_id)

    @classmethod
    async def delete_session(cls, session_id: str, user_id: str) -> None:
        await SessionService.delete_session(session_id, user_id)
