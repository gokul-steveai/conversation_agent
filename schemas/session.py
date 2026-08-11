from typing import Any, Dict, List

from langchain_core.messages import BaseMessage
from pydantic import BaseModel, Field


class CreateSessionRequest(BaseModel):
    """Request schema for creating a new session."""

    user_id: str = Field(..., description="Authenticated owner user ID")
    title: str = Field(default="New Onboarding Session", description="Session title")


class SaveSessionRequest(BaseModel):
    """Request schema for saving session state and history."""

    session_id: str = Field(..., description="Unique session ID")
    user_id: str = Field(..., description="Authenticated owner user ID")
    state: Dict[str, Any] = Field(..., description="Onboarding state dict")
    messages: List[Dict[str, Any]] = Field(..., description="UI message history")
    history_messages: List[BaseMessage] = Field(
        ..., description="LangChain BaseMessage history"
    )

    class Config:
        arbitrary_types_allowed = True


class SessionResponse(BaseModel):
    """Response schema summarizing a conversation session."""

    session_id: str
    user_id: str
    title: str
    created_at: str
    updated_at: str


class SessionDetailResponse(BaseModel):
    """Response schema containing full detail of a loaded conversation session."""

    session_id: str
    user_id: str
    title: str
    state: Dict[str, Any]
    messages: List[Dict[str, Any]]
    history_messages: List[BaseMessage]

    class Config:
        arbitrary_types_allowed = True
