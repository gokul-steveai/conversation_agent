from typing import Any, Dict, List, Optional, Tuple

from langchain_core.messages import BaseMessage

from services.session_service import SessionService


class MemoryService:
    """Facade for Async Session persistence and memory operations."""

    @classmethod
    async def create_session(cls, title: str = "New Onboarding Session") -> str:
        sess_id, _, _, _ = await SessionService.create_session(title)
        return sess_id

    @classmethod
    async def save_session(
        cls,
        session_id: str,
        title: str,
        state: Dict[str, Any],
        messages: List[Dict[str, Any]],
        history_messages: List[BaseMessage],
    ) -> None:
        await SessionService.save_session(session_id, state, messages, history_messages)

    @classmethod
    async def load_session(
        cls, session_id: str
    ) -> Optional[Tuple[Dict[str, Any], List[Dict[str, Any]], List[BaseMessage]]]:
        return await SessionService.load_session(session_id)

    @classmethod
    async def list_sessions(cls) -> List[Dict[str, Any]]:
        return await SessionService.list_sessions()

    @classmethod
    async def delete_session(cls, session_id: str) -> None:
        await SessionService.delete_session(session_id)
