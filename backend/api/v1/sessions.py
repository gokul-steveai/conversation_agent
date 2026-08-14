from typing import List

from api.deps import get_current_user, get_session_service
from fastapi import APIRouter, Depends, HTTPException
from schemas.auth import UserResponse
from schemas.session import (
    CreateSessionRequest,
    SaveSessionRequest,
    SessionDetailResponse,
    SessionResponse,
)
from services.session_service import SessionService

router = APIRouter(prefix="/sessions", tags=["Sessions"])


def resolve_effective_user_id(current_user: UserResponse) -> str:
    if current_user and current_user.user_id:
        return current_user.user_id
    raise HTTPException(status_code=401, detail="Authentication required")


@router.get("", response_model=List[SessionResponse])
async def list_sessions(
    current_user: UserResponse = Depends(get_current_user),
    session_service: SessionService = Depends(get_session_service),
):
    effective_user_id = resolve_effective_user_id(current_user)
    return await session_service.list_sessions(effective_user_id)


@router.post("", response_model=SessionDetailResponse)
async def create_session(
    request: CreateSessionRequest,
    current_user: UserResponse = Depends(get_current_user),
    session_service: SessionService = Depends(get_session_service),
):
    effective_user_id = resolve_effective_user_id(current_user)
    return await session_service.create_session(
        request_or_user_id=effective_user_id,
        title=request.title or "New Chat Session",
    )


@router.get("/{session_id}", response_model=SessionDetailResponse)
async def load_session(
    session_id: str,
    current_user: UserResponse = Depends(get_current_user),
    session_service: SessionService = Depends(get_session_service),
):
    effective_user_id = resolve_effective_user_id(current_user)
    session = await session_service.load_session(session_id, effective_user_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.post("/save")
async def save_session(
    request: SaveSessionRequest,
    current_user: UserResponse = Depends(get_current_user),
    session_service: SessionService = Depends(get_session_service),
):
    effective_user_id = resolve_effective_user_id(current_user)
    request.user_id = effective_user_id
    await session_service.save_session(request)
    return {"status": "success"}


@router.delete("/{session_id}")
async def delete_session(
    session_id: str,
    current_user: UserResponse = Depends(get_current_user),
    session_service: SessionService = Depends(get_session_service),
):
    effective_user_id = resolve_effective_user_id(current_user)
    await session_service.delete_session(session_id, effective_user_id)
    return {"status": "success"}
