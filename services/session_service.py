import json
import uuid
from typing import Any, Dict, List, Optional, Union

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    SystemMessage,
    messages_from_dict,
    messages_to_dict,
)

from config.constants import (
    DEFAULT_GREETING,
    NODE_PERSONAL_INFO,
    SYSTEM_PROMPT_PERSONAL_INFO,
)
from repositories.session_repository import SessionRepository
from repositories.user_repository import UserRepository
from schemas.session import (
    CreateSessionRequest,
    SaveSessionRequest,
    SessionDetailResponse,
    SessionResponse,
)
from utils.logger import logger


class SessionService:
    @classmethod
    def serialize_messages(cls, messages: List[BaseMessage]) -> str:
        """Serializes complete LangChain BaseMessage objects into JSON preserving tool_calls, IDs, and metadata."""
        message_dicts = messages_to_dict(messages)
        return json.dumps(message_dicts)

    @classmethod
    def deserialize_messages(cls, json_str: str) -> List[BaseMessage]:
        """Deserializes JSON string into LangChain BaseMessage objects, with seamless migration for legacy {type, content} records."""
        try:
            data = json.loads(json_str)
            if not isinstance(data, list) or not data:
                return []

            first = data[0]
            # Detect legacy format: {"type": "human", "content": "..."} lacking LangChain's "data" sub-dict
            if isinstance(first, dict) and "data" not in first and "content" in first:
                migrated_dicts = []
                for item in data:
                    m_type = item.get("type", "human")
                    content = item.get("content", "")
                    migrated_dicts.append(
                        {
                            "type": m_type,
                            "data": {
                                "content": content,
                                "additional_kwargs": {},
                                "response_metadata": {},
                            },
                        }
                    )
                return messages_from_dict(migrated_dicts)

            return messages_from_dict(data)
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
        cls,
        request_or_user_id: Union[CreateSessionRequest, str],
        title: str = "New Onboarding Session",
    ) -> SessionDetailResponse:
        if isinstance(request_or_user_id, CreateSessionRequest):
            user_id = request_or_user_id.user_id
            session_title = request_or_user_id.title
        else:
            user_id = request_or_user_id
            session_title = title

        if not user_id:
            raise ValueError("user_id must be provided to create a session.")

        # Ensure owner user record exists for FK integrity
        await UserRepository.get_or_create_user(user_id=user_id)

        session_id = str(uuid.uuid4())

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
            user_id=user_id,
            title=session_title,
            state_json=json.dumps(initial_state),
            messages_json=json.dumps(initial_messages),
            history_json=cls.serialize_messages(initial_history),
        )

        return SessionDetailResponse(
            session_id=session_id,
            user_id=user_id,
            title=session_title,
            state=initial_state,
            messages=initial_messages,
            history_messages=initial_history,
        )

    @classmethod
    async def save_session(cls, request: SaveSessionRequest) -> None:
        if not request.user_id:
            raise ValueError("user_id must be provided to save a session.")

        title = cls.format_title(request.state, request.session_id)
        state_json = json.dumps(request.state)
        messages_json = json.dumps(request.messages)
        history_json = cls.serialize_messages(request.history_messages)

        await SessionRepository.save_entity(
            session_id=request.session_id,
            user_id=request.user_id,
            title=title,
            state_json=state_json,
            messages_json=messages_json,
            history_json=history_json,
        )

    @classmethod
    async def load_session(
        cls, session_id: str, user_id: str
    ) -> Optional[SessionDetailResponse]:
        if not user_id:
            raise ValueError("user_id must be provided to load a session.")

        row = await SessionRepository.find_by_id(session_id, user_id)
        if row:
            state = json.loads(row.state_json)
            messages = json.loads(row.messages_json)
            history_messages = cls.deserialize_messages(row.history_json)
            return SessionDetailResponse(
                session_id=row.session_id,
                user_id=row.user_id,
                title=row.title,
                state=state,
                messages=messages,
                history_messages=history_messages,
            )
        return None

    @classmethod
    async def list_sessions(cls, user_id: str) -> List[SessionResponse]:
        if not user_id:
            raise ValueError("user_id must be provided to list sessions.")

        rows = await SessionRepository.find_all_by_user(user_id)
        sessions = []
        for row in rows:
            created_str = (
                row.created_at.isoformat()
                if hasattr(row.created_at, "isoformat")
                else str(row.created_at)
            )
            updated_str = (
                row.updated_at.isoformat()
                if hasattr(row.updated_at, "isoformat")
                else str(row.updated_at)
            )
            sessions.append(
                SessionResponse(
                    session_id=row.session_id,
                    user_id=row.user_id,
                    title=row.title,
                    created_at=created_str,
                    updated_at=updated_str,
                )
            )
        return sessions

    @classmethod
    async def delete_session(cls, session_id: str, user_id: str) -> None:
        if not user_id:
            raise ValueError("user_id must be provided to delete a session.")

        await SessionRepository.delete_by_id(session_id, user_id)
