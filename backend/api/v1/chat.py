import json
from typing import Any, Dict, Tuple

from api.deps import get_current_user
from controllers.chat_controller import ChatController
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from schemas.auth import UserResponse
from schemas.schemas import ChatMessageRequest, ChatMessageResponse, ToolLogItem
from schemas.session import SaveSessionRequest
from services.session_service import SessionService
from utils.logger import logger

router = APIRouter(prefix="/chat", tags=["Chat & Agents"])


async def _resolve_chat_context(
    request: ChatMessageRequest, current_user: UserResponse
) -> Tuple[str, Dict[str, Any], list, list]:
    user_id = current_user.user_id
    state = request.state or {}
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
    current_user: UserResponse = Depends(get_current_user),
):
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
        logger.error(f"Error processing chat message: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="An error occurred while processing your request."
        ) from e


@router.post("/stream")
async def stream_chat_message(
    request: ChatMessageRequest,
    current_user: UserResponse = Depends(get_current_user),
):

    async def token_generator():
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

            state_payload = json.dumps({"updated_state": state})
            yield f"event: state\ndata: {state_payload}\n\n"

            done_payload = json.dumps({"status": "completed"})
            yield f"event: done\ndata: {done_payload}\n\n"

        except Exception as e:
            logger.error(f"Error in SSE stream generator: {e}", exc_info=True)
            error_payload = json.dumps(
                {"error": "An error occurred while processing your request."}
            )
            yield f"event: error\ndata: {error_payload}\n\n"

    return StreamingResponse(token_generator(), media_type="text/event-stream")
