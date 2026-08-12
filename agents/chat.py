from datetime import datetime, timezone
from typing import Any, Dict

from langchain_core.messages import SystemMessage

from core.llm_factory import llm
from prompts.system_prompts import SYSTEM_PROMPT_CHAT
from schemas.state import ChatState
from utils.sanitizer import sanitize_response


async def chat_agent(state: ChatState) -> Dict[str, Any]:
    name = state.get("name") or "User"
    location = state.get("location") or "Not specified"
    topics = state.get("topic_preferences") or []
    topics_str = ", ".join(topics) if topics else "General"
    current_time_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    sys_prompt = SystemMessage(
        SYSTEM_PROMPT_CHAT.format(
            name=name,
            location=location,
            topics=topics_str,
            current_time=current_time_str,
        )
    )

    messages = [sys_prompt] + list(state.get("messages", []))
    res = await llm.ainvoke(messages)
    clean_reply = sanitize_response(res.content)

    return {"engagement_response": clean_reply}
