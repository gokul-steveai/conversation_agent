from api.deps import get_chat_controller, get_current_user, get_session_service
from controllers.chat_controller import ChatController
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from schemas.auth import UserResponse
from schemas.schemas import ChatMessageRequest, ChatMessageResponse, ToolLogItem
from schemas.session import SaveSessionRequest
from services.session_service import SessionService
from utils.chat_utils import format_sse_event, resolve_chat_context
from utils.logger import logger

router = APIRouter(prefix="/chat", tags=["Chat & Agents"])


@router.post("/message", response_model=ChatMessageResponse)
async def process_chat_message(
    request: ChatMessageRequest,
    current_user: UserResponse = Depends(get_current_user),
    session_service: SessionService = Depends(get_session_service),
    chat_controller: ChatController = Depends(get_chat_controller),
):
    try:
        user_id, state, history, messages = await resolve_chat_context(
            request, current_user, session_service=session_service
        )

        reply, tool_logs = await chat_controller.process_step(
            user_text=request.user_text, state=state, history_messages=history
        )

        messages.append({"role": "user", "content": request.user_text})
        for log in tool_logs:
            messages.append(log)
        messages.append({"role": "assistant", "content": reply})

        await session_service.save_session(
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
    session_service: SessionService = Depends(get_session_service),
    chat_controller: ChatController = Depends(get_chat_controller),
):
    async def token_generator():
        try:
            user_id, state, history, messages = await resolve_chat_context(
                request, current_user, session_service=session_service
            )

            messages.append({"role": "user", "content": request.user_text})
            tool_logs = []
            full_reply_acc = []

            async for event in chat_controller.process_step_stream(
                user_text=request.user_text, state=state, history_messages=history
            ):
                evt_type = event.get("type")
                if evt_type == "tool":
                    content = event.get("content", "")
                    tool_logs.append({"role": "tool", "content": content})
                    yield format_sse_event("tool", {"content": content})
                elif evt_type == "token":
                    chunk = event.get("content", "")
                    full_reply_acc.append(chunk)
                    yield format_sse_event("message", {"chunk": chunk})
                elif evt_type == "state":
                    updated_st = event.get("updated_state", state)
                    state = updated_st
                    yield format_sse_event("state", {"updated_state": state})

            full_reply = "".join(full_reply_acc)
            for log in tool_logs:
                messages.append(log)
            messages.append({"role": "assistant", "content": full_reply})

            await session_service.save_session(
                SaveSessionRequest(
                    session_id=request.session_id,
                    user_id=user_id,
                    state=state,
                    messages=messages,
                    history_messages=history,
                )
            )

            yield format_sse_event("done", {"status": "completed"})

        except Exception as e:
            logger.error(f"Error in SSE stream generator: {e}", exc_info=True)
            yield format_sse_event(
                "error", {"error": "An error occurred while processing your request."}
            )

    return StreamingResponse(token_generator(), media_type="text/event-stream")
