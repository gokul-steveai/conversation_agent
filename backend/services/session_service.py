import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Union

from config.constants import (
    DEFAULT_GREETING,
    NODE_CHAT,
)
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    SystemMessage,
    messages_from_dict,
    messages_to_dict,
)
from prompts import SYSTEM_PROMPT_CHAT
from repositories import SessionRepository, UserRepository
from schemas import (
    CreateSessionRequest,
    SaveSessionRequest,
    SessionDetailResponse,
    SessionResponse,
)
from utils import logger, sanitize_response


class SessionService:
    @classmethod
    def serialize_messages(cls, messages: Sequence[BaseMessage]) -> str:
        """Serializes complete LangChain BaseMessage objects into JSON preserving tool_calls, IDs, and metadata."""
        message_dicts = messages_to_dict(messages)
        return json.dumps(message_dicts)

    @classmethod
    def deserialize_messages(cls, json_str: str) -> List[BaseMessage]:
        try:
            data = json.loads(json_str)
            if not isinstance(data, list) or not data:
                return []

            first = data[0]
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
    def _fallback_heuristic_title(
        cls, first_user_text: str, existing_title: str = ""
    ) -> str:
        import re

        cleaned = re.sub(
            r"^(do you know about|tell me about|what is|what are|can you explain|how do i|please|how to|i want to know about|could you explain|what do you know about)\s+",
            "",
            first_user_text,
            flags=re.IGNORECASE,
        ).strip()

        if not cleaned:
            cleaned = first_user_text

        cleaned = cleaned.rstrip("?.! ")
        words = cleaned.split()
        if len(words) > 5:
            short_title = " ".join(words[:5]) + "..."
        else:
            short_title = " ".join(words)

        if short_title:
            short_title = short_title[0].upper() + short_title[1:]
        else:
            short_title = "Chat Session"

        return short_title[:45]

    @classmethod
    async def generate_llm_title(
        cls, messages: List[Dict[str, Any]], existing_title: str = ""
    ) -> str:
        if existing_title and existing_title not in ["New Chat Session", ""]:
            if (
                not existing_title.startswith("Session -")
                and "from" not in existing_title
                and not existing_title.startswith("Session ")
            ):
                return existing_title

        first_user_text = ""
        for msg in messages:
            if isinstance(msg, dict) and msg.get("role") == "user":
                raw_user_content = msg.get("content")
                content = (
                    sanitize_response(raw_user_content).strip()
                    if raw_user_content
                    else ""
                )
                if content:
                    first_user_text = content
                    break

        if not first_user_text:
            return existing_title or "New Chat Session"

        try:
            from core.llm_factory import llm
            from langchain_core.messages import HumanMessage, SystemMessage

            prompt = (
                "You are an expert concise title generator.\n"
                "Generate a short, punchy, professional title (3 to 5 words max) summarizing the topic of the following user query.\n"
                "Rules:\n"
                "1. Output ONLY the plain title text with NO quotes, NO markdown, NO prefixes (like 'Title:'), and NO ending punctuation.\n"
                "2. Keep it strictly between 2 and 5 words."
            )
            res = await llm.ainvoke(
                [SystemMessage(content=prompt), HumanMessage(content=first_user_text)]
            )
            raw_title = (
                sanitize_response(res.content)
                if res and res.content is not None
                else ""
            )
            title = raw_title.strip().replace('"', "").replace("'", "")
            title = title.lstrip("#*` ").rstrip(".!?")
            if title and len(title) >= 3:
                return title[:45]
        except Exception as e:
            logger.warning(f"LLM title generation failed, using heuristic: {e}")

        return cls._fallback_heuristic_title(first_user_text, existing_title)

    @classmethod
    def format_title(
        cls, messages: List[Dict[str, Any]], existing_title: str = ""
    ) -> str:
        user_content = next(
            (
                sanitize_response(m.get("content") or "")
                for m in messages
                if isinstance(m, dict) and m.get("role") == "user" and m.get("content")
            ),
            "",
        )
        return cls._fallback_heuristic_title(
            user_content,
            existing_title=existing_title,
        )

    @classmethod
    async def create_session(
        cls,
        request_or_user_id: Union[CreateSessionRequest, str],
        title: str = "New Chat Session",
    ) -> SessionDetailResponse:
        if isinstance(request_or_user_id, CreateSessionRequest):
            user_id = request_or_user_id.user_id
            session_title = request_or_user_id.title
        else:
            user_id = request_or_user_id
            session_title = title

        if not user_id:
            raise ValueError("user_id must be provided to create a session.")

        await UserRepository.get_or_create_user(user_id=user_id)

        session_id = str(uuid.uuid4())
        current_time_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

        initial_state = {
            "user_id": user_id,
            "name": "",
            "location": "",
            "topic_preferences": [],
            "current_agent": NODE_CHAT,
        }
        initial_messages = [{"role": "assistant", "content": DEFAULT_GREETING}]
        initial_history: List[BaseMessage] = [
            SystemMessage(
                SYSTEM_PROMPT_CHAT.format(
                    name="User",
                    location="Not specified",
                    topics="General",
                    current_time=current_time_str,
                )
            ),
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

        existing = await SessionRepository.find_by_session_and_user_id(
            request.session_id, request.user_id
        )
        existing_title = existing.title if existing else ""

        title = await cls.generate_llm_title(
            request.messages, existing_title=existing_title
        )
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

        row = await SessionRepository.find_by_session_and_user_id(session_id, user_id)
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

        await SessionRepository.delete_by_session_id_and_user_id(session_id, user_id)
