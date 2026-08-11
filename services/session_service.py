import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from config.constants import (
    DEFAULT_GREETING,
    NODE_PERSONAL_INFO,
    SYSTEM_PROMPT_PERSONAL_INFO,
)
from repositories.session_repository import SessionRepository
from utils.logger import logger


class SessionService:
    """Domain Service owning Async Session lifecycle management, validation, and domain logic."""

    @classmethod
    def serialize_messages(cls, messages: List[BaseMessage]) -> str:
        serialized = []
        for msg in messages:
            if isinstance(msg, SystemMessage):
                serialized.append({"type": "system", "content": msg.content})
            elif isinstance(msg, HumanMessage):
                serialized.append({"type": "human", "content": msg.content})
            elif isinstance(msg, AIMessage):
                serialized.append({"type": "ai", "content": msg.content})
        return json.dumps(serialized)

    @classmethod
    def deserialize_messages(cls, json_str: str) -> List[BaseMessage]:
        try:
            data = json.loads(json_str)
            messages = []
            for item in data:
                m_type = item.get("type")
                content = item.get("content", "")
                if m_type == "system":
                    messages.append(SystemMessage(content))
                elif m_type == "human":
                    messages.append(HumanMessage(content))
                elif m_type == "ai":
                    messages.append(AIMessage(content))
            return messages
        except Exception as e:
            logger.error(f"Error deserializing history messages: {e}")
            return []

    @classmethod
    def format_title(cls, state: Dict[str, Any], session_id: str) -> str:
        name = state.get("name")
        loc = state.get("location")
        if name and loc:
            return f"{name} from {loc}"
        elif name:
            return f"Session - {name}"
        return f"Session {session_id[:8]}"

    @classmethod
    async def create_session(
        cls, title: str = "New Onboarding Session"
    ) -> Tuple[str, Dict[str, Any], List[Dict[str, Any]], List[BaseMessage]]:
        session_id = str(uuid.uuid4())
        now = datetime.now().isoformat()

        initial_state = {
            "name": "",
            "location": "",
            "topic_preferences": [],
            "engagement_response": "",
            "current_agent": NODE_PERSONAL_INFO,
            "completed": False,
        }
        initial_messages = [{"role": "assistant", "content": DEFAULT_GREETING}]
        initial_history = [
            SystemMessage(SYSTEM_PROMPT_PERSONAL_INFO),
            AIMessage(DEFAULT_GREETING),
        ]

        await SessionRepository.save_entity(
            session_id=session_id,
            title=title,
            state_json=json.dumps(initial_state),
            messages_json=json.dumps(initial_messages),
            history_json=cls.serialize_messages(initial_history),
            created_at=now,
            updated_at=now,
        )
        return session_id, initial_state, initial_messages, initial_history

    @classmethod
    async def save_session(
        cls,
        session_id: str,
        state: Dict[str, Any],
        messages: List[Dict[str, Any]],
        history_messages: List[BaseMessage],
    ) -> None:
        now = datetime.now().isoformat()
        title = cls.format_title(state, session_id)
        state_json = json.dumps(state)
        messages_json = json.dumps(messages)
        history_json = cls.serialize_messages(history_messages)

        existing = await SessionRepository.find_by_id(session_id)
        created_at = existing.created_at if existing else now

        await SessionRepository.save_entity(
            session_id=session_id,
            title=title,
            state_json=state_json,
            messages_json=messages_json,
            history_json=history_json,
            created_at=created_at,
            updated_at=now,
        )

    @classmethod
    async def load_session(
        cls, session_id: str
    ) -> Optional[Tuple[Dict[str, Any], List[Dict[str, Any]], List[BaseMessage]]]:
        row = await SessionRepository.find_by_id(session_id)
        if row:
            state = json.loads(row.state_json)
            messages = json.loads(row.messages_json)
            history_messages = cls.deserialize_messages(row.history_json)
            return state, messages, history_messages
        return None

    @classmethod
    async def list_sessions(cls) -> List[Dict[str, Any]]:
        rows = await SessionRepository.find_all()
        return [
            {
                "session_id": row.session_id,
                "title": row.title,
                "created_at": row.created_at,
                "updated_at": row.updated_at,
            }
            for row in rows
        ]

    @classmethod
    async def delete_session(cls, session_id: str) -> None:
        await SessionRepository.delete_by_id(session_id)
