import json
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Tuple

from core.llm_factory import ainvoke_structured, llm
from langchain_core.messages import BaseMessage, SystemMessage
from prompts import SYSTEM_PROMPT_SEARCH_EVALUATION
from schemas.auth import UserResponse
from schemas.schemas import ChatDecision, ChatMessageRequest, StateUpdate

if TYPE_CHECKING:
    from services.session_service import SessionService

from langfuse import observe


def extract_state_str(state: Dict[str, Any], keys: List[str], default: str = "") -> str:
    """Extracts the first valid non-empty string value for key candidates in state dict."""
    for key in keys:
        val = state.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return default


def merge_state_topics(state: Dict[str, Any], new_topics: List[str]) -> None:
    """Deduplicates and merges new topic strings into state['topic_preferences']."""
    if not new_topics:
        return
    existing_raw = state.get("topic_preferences", [])
    existing: List[str] = existing_raw if isinstance(existing_raw, list) else []
    cleaned_new = [t.strip() for t in new_topics if isinstance(t, str) and t.strip()]
    if cleaned_new:
        state["topic_preferences"] = list(dict.fromkeys(existing + cleaned_new))


async def resolve_chat_context(
    request: ChatMessageRequest,
    current_user: UserResponse,
    session_service: "SessionService",
) -> Tuple[str, Dict[str, Any], List[BaseMessage], List[Dict[str, Any]]]:
    user_id = current_user.user_id
    state = request.state or {}
    state["user_id"] = user_id
    state["session_id"] = request.session_id

    existing = await session_service.load_session(request.session_id, user_id)
    if existing:
        history_messages = existing.history_messages
        messages = existing.messages
        current_state = existing.state
        current_state.update(state)
    else:
        history_messages = []
        messages = []
        current_state = state

    current_state["session_id"] = request.session_id
    return user_id, current_state, history_messages, messages


def format_sse_event(event_type: str, data: Dict[str, Any]) -> str:
    payload = json.dumps(data)
    return f"event: {event_type}\ndata: {payload}\n\n"


def bound_history(
    history_messages: List[BaseMessage], max_recent: int = 12
) -> List[BaseMessage]:
    non_system_messages = [
        message
        for message in history_messages
        if not isinstance(message, SystemMessage)
    ]
    return non_system_messages[-max_recent:]


def prepare_user_context(state: Dict[str, Any]) -> Tuple[str, str, str, str, str]:
    session_id = extract_state_str(state, ["session_id", "thread_id"], default="")
    user_name = extract_state_str(state, ["name"], default="User")
    user_location = extract_state_str(state, ["location"], default="Not specified")

    user_topics_val = state.get("topic_preferences") or []
    user_topics = user_topics_val if isinstance(user_topics_val, list) else []
    formatted_topics = ", ".join(user_topics) if user_topics else "General"
    formatted_current_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    return (
        session_id,
        user_name,
        user_location,
        formatted_topics,
        formatted_current_time,
    )


def refine_search_query(
    decision: ChatDecision, user_text: str, user_location: str
) -> Tuple[str, bool]:
    search_query = (decision.search_query or "").strip()
    if not search_query and decision.needs_web_search and user_text.strip():
        search_query = user_text.strip()

    if decision.query_location and decision.query_location.strip():
        target_location = decision.query_location.strip()
        if target_location.lower() not in search_query.lower():
            search_query = f"{target_location} {search_query}"
    elif (
        user_location != "Not specified"
        and user_location.lower() not in search_query.lower()
    ):
        if any(
            keyword in search_query.lower()
            for keyword in [
                "my location",
                "current location",
                "here",
                "local",
                "weather",
            ]
        ):
            search_query = f"{user_location} {search_query}"

    is_search_required = decision.needs_web_search and bool(search_query)
    return search_query, is_search_required


async def update_user_context_from_history(
    history_messages: List[BaseMessage],
    state: Dict[str, Any],
) -> None:
    try:
        refined: StateUpdate = await ainvoke_structured(
            llm, StateUpdate, history_messages
        )
        if refined.name and refined.name.strip():
            state["name"] = refined.name.strip()
        if refined.location and refined.location.strip():
            state["location"] = refined.location.strip()
        if refined.topics:
            merge_state_topics(state, refined.topics)
    except Exception:
        pass


@observe(name="evaluate_search_decision", as_type="chain", capture_input=False)
async def evaluate_search_prompt(
    user_name: str,
    user_location: str,
    user_text: str,
    history_messages: List[BaseMessage],
) -> ChatDecision:
    bounded = bound_history(history_messages, max_recent=6)
    system_msg = SystemMessage(
        SYSTEM_PROMPT_SEARCH_EVALUATION.format(
            user_name=user_name,
            user_loc=user_location,
            user_text=user_text,
        )
    )
    evaluation_messages = [system_msg] + bounded
    return await ainvoke_structured(llm, ChatDecision, evaluation_messages)
