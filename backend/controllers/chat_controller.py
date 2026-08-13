from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from core.database import DatabaseManager
from core.llm_factory import ainvoke_structured, llm
from core.observability import langfuse_handler
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from prompts import (
    HUMAN_PROMPT_UNTRUSTED_WEB_DATA,
    SYSTEM_PROMPT_DIRECT_CHAT,
    SYSTEM_PROMPT_SEARCH_EVALUATION,
    SYSTEM_PROMPT_WEB_SYNTHESIS,
)
from schemas.schemas import ChatDecision, StateUpdate
from services import SearchService
from utils import sanitize_response
from utils.helper import MemoryManager


class ChatController:
    @classmethod
    def _get_memory_manager(cls) -> Optional[MemoryManager]:
        if DatabaseManager._SessionLocal:
            return MemoryManager(DatabaseManager._SessionLocal)
        return None

    @classmethod
    async def _save_message_memory(
        cls, session_id: str, content: str, role: str
    ) -> None:
        if not session_id:
            return
        try:
            mgr = cls._get_memory_manager()
            if mgr:
                await mgr.write_conversational_memory(
                    content=content, role=role, thread_id=session_id
                )
        except Exception:
            pass

    @classmethod
    async def _save_tool_log(
        cls, session_id: str, tool_name: str, tool_args: Any, result: str
    ) -> None:
        if not session_id:
            return
        try:
            mgr = cls._get_memory_manager()
            if mgr:
                await mgr.write_tool_log(
                    thread_id=session_id,
                    tool_name=tool_name,
                    tool_args=tool_args,
                    result=result,
                    status="success",
                )
        except Exception:
            pass

    @classmethod
    def _bound_history(cls, history_messages: list, max_recent: int = 12) -> list:
        if len(history_messages) <= max_recent:
            return history_messages

        system_msgs = [
            msg for msg in history_messages if isinstance(msg, SystemMessage)
        ]
        non_system_msgs = [
            msg for msg in history_messages if not isinstance(msg, SystemMessage)
        ]
        return system_msgs + non_system_msgs[-max_recent:]

    @classmethod
    async def _update_user_context_from_history(
        cls, history_messages: list, state: Dict[str, Any]
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
                existing = state.get("topic_preferences", [])
                new_topics = [t.strip() for t in refined.topics if t.strip()]
                state["topic_preferences"] = list(dict.fromkeys(existing + new_topics))
        except Exception:
            pass

    @classmethod
    async def _evaluate_prompt(
        cls, user_name: str, user_location: str, user_text: str
    ) -> ChatDecision:
        eval_messages = [
            SystemMessage(
                SYSTEM_PROMPT_SEARCH_EVALUATION.format(
                    user_name=user_name,
                    user_loc=user_location,
                    user_text=user_text,
                )
            )
        ]
        return await ainvoke_structured(llm, ChatDecision, eval_messages)

    @classmethod
    def _refine_search_query(
        cls, decision: ChatDecision, user_text: str, user_location: str
    ) -> Tuple[str, bool]:
        query = (decision.search_query or "").strip()
        if not query and decision.needs_web_search and user_text.strip():
            query = user_text.strip()

        if decision.query_location and decision.query_location.strip():
            target_loc = decision.query_location.strip()
            if target_loc.lower() not in query.lower():
                query = f"{target_loc} {query}"
        elif (
            user_location != "Not specified"
            and user_location.lower() not in query.lower()
        ):
            if any(
                kw in query.lower()
                for kw in [
                    "my location",
                    "current location",
                    "here",
                    "local",
                    "weather",
                ]
            ):
                query = f"{user_location} {query}"

        is_required = decision.needs_web_search and bool(query)
        return query, is_required

    @classmethod
    async def _invoke_and_record_reply(
        cls, messages: list, history_messages: list, session_id: str = ""
    ) -> str:
        res = await llm.ainvoke(messages, config={"callbacks": [langfuse_handler]})
        reply = sanitize_response(res.content)
        history_messages.append(AIMessage(reply))
        await cls._save_message_memory(session_id, reply, role="assistant")
        return reply

    @classmethod
    async def _execute_search_flow(
        cls,
        search_query: str,
        user_name: str,
        user_loc: str,
        topics_str: str,
        time_str: str,
        history_messages: list,
        session_id: str = "",
    ) -> Tuple[str, list]:
        tool_logs = [
            {
                "role": "tool",
                "content": f"🔍 [Tavily Search] Autonomously searching live web data: '{search_query}'...",
            }
        ]
        web_data = await SearchService.asearch_general(search_query)
        await cls._save_tool_log(
            session_id, "tavily_search", {"query": search_query}, web_data
        )

        sys_msg = SystemMessage(
            SYSTEM_PROMPT_WEB_SYNTHESIS.format(
                user_name=user_name,
                user_loc=user_loc,
                topics_str=topics_str,
                current_time_str=time_str,
            )
        )
        web_msg = HumanMessage(
            HUMAN_PROMPT_UNTRUSTED_WEB_DATA.format(
                query_str=search_query, search_data=web_data
            )
        )
        bounded_history = cls._bound_history(history_messages)
        reply = await cls._invoke_and_record_reply(
            [sys_msg] + bounded_history + [web_msg],
            history_messages,
            session_id=session_id,
        )
        return reply, tool_logs

    @classmethod
    async def _execute_direct_flow(
        cls,
        user_name: str,
        user_loc: str,
        topics_str: str,
        time_str: str,
        history_messages: list,
        session_id: str = "",
    ) -> Tuple[str, list]:
        sys_msg = SystemMessage(
            SYSTEM_PROMPT_DIRECT_CHAT.format(
                user_name=user_name,
                user_loc=user_loc,
                topics_str=topics_str,
                current_time_str=time_str,
            )
        )
        bounded_history = cls._bound_history(history_messages)
        reply = await cls._invoke_and_record_reply(
            [sys_msg] + bounded_history, history_messages, session_id=session_id
        )
        return reply, []

    @classmethod
    async def process_step(
        cls,
        user_text: str,
        state: Dict[str, Any],
        history_messages: list,
    ) -> Tuple[str, list]:
        session_id = state.get("session_id") or state.get("thread_id") or ""
        history_messages.append(HumanMessage(user_text))
        await cls._save_message_memory(session_id, user_text, role="user")

        await cls._update_user_context_from_history(history_messages, state)

        user_name = state.get("name") or "User"
        user_loc = state.get("location") or "Not specified"
        topics = state.get("topic_preferences") or []
        topics_str = ", ".join(topics) if topics else "General"
        time_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

        decision = await cls._evaluate_prompt(user_name, user_loc, user_text)

        if decision.declared_user_location and decision.declared_user_location.strip():
            user_loc = decision.declared_user_location.strip()
            state["location"] = user_loc

        if decision.needs_clarification and decision.clarification_question:
            clarification = decision.clarification_question.strip()
            history_messages.append(AIMessage(clarification))
            await cls._save_message_memory(session_id, clarification, role="assistant")
            return clarification, []

        query, is_search = cls._refine_search_query(decision, user_text, user_loc)

        if is_search:
            return await cls._execute_search_flow(
                query,
                user_name,
                user_loc,
                topics_str,
                time_str,
                history_messages,
                session_id=session_id,
            )

        return await cls._execute_direct_flow(
            user_name,
            user_loc,
            topics_str,
            time_str,
            history_messages,
            session_id=session_id,
        )
