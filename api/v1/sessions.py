from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from api.deps import get_current_user_optional
from schemas.auth import UserResponse
from schemas.session import (
    CreateSessionRequest,
    SaveSessionRequest,
    SessionDetailResponse,
    SessionResponse,
)
from services.session_service import SessionService

router = APIRouter(prefix="/sessions", tags=["Sessions"])


def resolve_effective_user_id(
    user_id: Optional[str], current_user: Optional[UserResponse]
) -> str:
    if user_id and user_id.strip():
        return user_id.strip()
    if current_user and current_user.user_id:
        return current_user.user_id
    return "default_user"


@router.get("", response_model=List[SessionResponse])
async def list_sessions(
    user_id: Optional[str] = Query(None),
    current_user: Optional[UserResponse] = Depends(get_current_user_optional),
):
    effective_user_id = resolve_effective_user_id(user_id, current_user)
    return await SessionService.list_sessions(effective_user_id)


@router.post("", response_model=SessionDetailResponse)
async def create_session(
    request: CreateSessionRequest,
    current_user: Optional[UserResponse] = Depends(get_current_user_optional),
):
    effective_user_id = resolve_effective_user_id(request.user_id, current_user)
    return await SessionService.create_session(
        request_or_user_id=effective_user_id, title=request.title or "New Chat Session"
    )


@router.get("/{session_id}", response_model=SessionDetailResponse)
async def load_session(
    session_id: str,
    user_id: Optional[str] = Query(None),
    current_user: Optional[UserResponse] = Depends(get_current_user_optional),
):
    effective_user_id = resolve_effective_user_id(user_id, current_user)
    session = await SessionService.load_session(session_id, effective_user_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.post("/save")
async def save_session(
    request: SaveSessionRequest,
    current_user: Optional[UserResponse] = Depends(get_current_user_optional),
):
    effective_user_id = resolve_effective_user_id(request.user_id, current_user)
    request.user_id = effective_user_id
    await SessionService.save_session(request)
    return {"status": "success"}


@router.delete("/{session_id}")
async def delete_session(
    session_id: str,
    user_id: Optional[str] = Query(None),
    current_user: Optional[UserResponse] = Depends(get_current_user_optional),
):
    effective_user_id = resolve_effective_user_id(user_id, current_user)
    await SessionService.delete_session(session_id, effective_user_id)
    return {"status": "success"}
