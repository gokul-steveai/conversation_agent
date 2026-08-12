import json
from typing import Any, Dict, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from api.deps import get_current_user_optional
from controllers.chat_controller import ChatController
from schemas.auth import UserResponse
from schemas.schemas import ChatMessageRequest, ChatMessageResponse, ToolLogItem
from schemas.session import SaveSessionRequest
from services.session_service import SessionService

router = APIRouter(prefix="/chat", tags=["Chat & Agents"])


async def _resolve_chat_context(
    request: ChatMessageRequest, current_user: Optional[UserResponse]
) -> Tuple[str, Dict[str, Any], list, list]:
    """Helper method resolving effective user_id, active session state, and message history."""
    state = request.state or {}
    user_id = (
        state.get("user_id")
        or (current_user.user_id if current_user else None)
        or "default_user"
    )
    state["user_id"] = user_id

    existing = await SessionService.load_session(request.session_id, user_id)
    if existing:
        history_messages = existing.history_messages
        messages = existing.messages
        current_state = existing.state
        current_state.update(state)
    else:
        history_messages = []
        messages = []
        current_state = state

    return user_id, current_state, history_messages, messages


@router.post("/message", response_model=ChatMessageResponse)
async def process_chat_message(
    request: ChatMessageRequest,
    current_user: Optional[UserResponse] = Depends(get_current_user_optional),
):
    """Processes non-streaming chat requests with full state and session persistence."""
    try:
        user_id, state, history, messages = await _resolve_chat_context(
            request, current_user
        )

        reply, tool_logs = await ChatController.process_step(
            user_text=request.user_text, state=state, history_messages=history
        )

        messages.append({"role": "user", "content": request.user_text})
        for log in tool_logs:
            messages.append(log)
        messages.append({"role": "assistant", "content": reply})

        await SessionService.save_session(
            SaveSessionRequest(
                session_id=request.session_id,
                user_id=user_id,
                state=state,
                messages=messages,
                history_messages=history,
            )
        )

        tool_log_items = [
            ToolLogItem(role=log.get("role", "tool"), content=log.get("content", ""))
            for log in tool_logs
        ]

        return ChatMessageResponse(
            reply=reply, tool_logs=tool_log_items, updated_state=state
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat execution error: {str(e)}")


@router.post("/stream")
async def stream_chat_message(
    request: ChatMessageRequest,
    current_user: Optional[UserResponse] = Depends(get_current_user_optional),
):

    async def token_generator():
        user_id, state, history, messages = await _resolve_chat_context(
            request, current_user
        )

        reply, tool_logs = await ChatController.process_step(
            user_text=request.user_text, state=state, history_messages=history
        )

        messages.append({"role": "user", "content": request.user_text})

        for log in tool_logs:
            messages.append(log)
            log_payload = json.dumps({"content": log.get("content", "")})
            yield f"event: tool\ndata: {log_payload}\n\n"

        words = reply.split(" ")
        for i, word in enumerate(words):
            chunk = word + (" " if i < len(words) - 1 else "")
            chunk_payload = json.dumps({"chunk": chunk})
            yield f"event: message\ndata: {chunk_payload}\n\n"

        messages.append({"role": "assistant", "content": reply})
        await SessionService.save_session(
            SaveSessionRequest(
                session_id=request.session_id,
                user_id=user_id,
                state=state,
                messages=messages,
                history_messages=history,
            )
        )

    return StreamingResponse(token_generator(), media_type="text/event-stream")
