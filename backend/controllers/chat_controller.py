from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from core.database import DatabaseManager
from core.llm_factory import ainvoke_structured, llm
from core.observability import langfuse_handler
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
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
            memory_manager = cls._get_memory_manager()
            if memory_manager:
                await memory_manager.write_conversational_memory(
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
            memory_manager = cls._get_memory_manager()
            if memory_manager:
                await memory_manager.write_tool_log(
                    thread_id=session_id,
                    tool_name=tool_name,
                    tool_args=tool_args,
                    result=result,
                    status="success",
                )
        except Exception:
            pass

    @classmethod
    def _bound_history(
        cls, history_messages: List[BaseMessage], max_recent: int = 12
    ) -> List[BaseMessage]:
        if len(history_messages) <= max_recent:
            return history_messages

        system_messages = [
            message
            for message in history_messages
            if isinstance(message, SystemMessage)
        ]
        non_system_messages = [
            message
            for message in history_messages
            if not isinstance(message, SystemMessage)
        ]
        return system_messages + non_system_messages[-max_recent:]

    @classmethod
    async def _update_user_context_from_history(
        cls, history_messages: List[BaseMessage], state: Dict[str, Any]
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
                existing_topics = state.get("topic_preferences", [])
                new_topics = [
                    topic.strip() for topic in refined.topics if topic.strip()
                ]
                state["topic_preferences"] = list(
                    dict.fromkeys(existing_topics + new_topics)
                )
        except Exception:
            pass

    @classmethod
    async def _evaluate_prompt(
        cls, user_name: str, user_location: str, user_text: str
    ) -> ChatDecision:
        evaluation_messages = [
            SystemMessage(
                SYSTEM_PROMPT_SEARCH_EVALUATION.format(
                    user_name=user_name,
                    user_loc=user_location,
                    user_text=user_text,
                )
            )
        ]
        return await ainvoke_structured(llm, ChatDecision, evaluation_messages)

    @classmethod
    def _refine_search_query(
        cls, decision: ChatDecision, user_text: str, user_location: str
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

    @classmethod
    async def _invoke_and_record_reply(
        cls,
        messages: List[BaseMessage],
        history_messages: List[BaseMessage],
        session_id: str = "",
    ) -> str:
        llm_response = await llm.ainvoke(
            messages, config={"callbacks": [langfuse_handler]}
        )
        assistant_reply = sanitize_response(llm_response.content)
        history_messages.append(AIMessage(assistant_reply))
        await cls._save_message_memory(session_id, assistant_reply, role="assistant")
        return assistant_reply

    @classmethod
    async def _execute_search_flow(
        cls,
        search_query: str,
        user_name: str,
        user_location: str,
        formatted_topics: str,
        formatted_current_time: str,
        history_messages: List[BaseMessage],
        session_id: str = "",
    ) -> Tuple[str, List[Dict[str, Any]]]:
        tool_logs: List[Dict[str, Any]] = [
            {
                "role": "tool",
                "content": f"🔍 [Tavily Search] Autonomously searching live web data: '{search_query}'...",
            }
        ]
        retrieved_web_data = await SearchService.asearch_general(search_query)
        await cls._save_tool_log(
            session_id, "tavily_search", {"query": search_query}, retrieved_web_data
        )

        system_message = SystemMessage(
            SYSTEM_PROMPT_WEB_SYNTHESIS.format(
                user_name=user_name,
                user_loc=user_location,
                topics_str=formatted_topics,
                current_time_str=formatted_current_time,
            )
        )
        web_search_message = HumanMessage(
            HUMAN_PROMPT_UNTRUSTED_WEB_DATA.format(
                query_str=search_query, search_data=retrieved_web_data
            )
        )
        bounded_history = cls._bound_history(history_messages)
        assistant_reply = await cls._invoke_and_record_reply(
            [system_message] + bounded_history + [web_search_message],
            history_messages,
            session_id=session_id,
        )
        return assistant_reply, tool_logs

    @classmethod
    async def _execute_direct_flow(
        cls,
        user_name: str,
        user_location: str,
        formatted_topics: str,
        formatted_current_time: str,
        history_messages: List[BaseMessage],
        session_id: str = "",
    ) -> Tuple[str, List[Dict[str, Any]]]:
        system_message = SystemMessage(
            SYSTEM_PROMPT_DIRECT_CHAT.format(
                user_name=user_name,
                user_loc=user_location,
                topics_str=formatted_topics,
                current_time_str=formatted_current_time,
            )
        )
        bounded_history = cls._bound_history(history_messages)
        assistant_reply = await cls._invoke_and_record_reply(
            [system_message] + bounded_history,
            history_messages,
            session_id=session_id,
        )
        return assistant_reply, []

    @classmethod
    async def process_step(
        cls,
        user_text: str,
        state: Dict[str, Any],
        history_messages: List[BaseMessage],
    ) -> Tuple[str, List[Dict[str, Any]]]:
        session_id = state.get("session_id") or state.get("thread_id") or ""
        history_messages.append(HumanMessage(user_text))
        await cls._save_message_memory(session_id, user_text, role="user")

        await cls._update_user_context_from_history(history_messages, state)

        user_name = state.get("name") or "User"
        user_location = state.get("location") or "Not specified"
        user_topics = state.get("topic_preferences") or []
        formatted_topics = ", ".join(user_topics) if user_topics else "General"
        formatted_current_time = datetime.now(timezone.utc).strftime(
            "%Y-%m-%d %H:%M UTC"
        )

        decision = await cls._evaluate_prompt(user_name, user_location, user_text)

        if decision.declared_user_location and decision.declared_user_location.strip():
            user_location = decision.declared_user_location.strip()
            state["location"] = user_location

        if decision.needs_clarification and decision.clarification_question:
            clarification_question = decision.clarification_question.strip()
            history_messages.append(AIMessage(clarification_question))
            await cls._save_message_memory(
                session_id, clarification_question, role="assistant"
            )
            return clarification_question, []

        search_query, is_search_required = cls._refine_search_query(
            decision, user_text, user_location
        )

        if is_search_required:
            return await cls._execute_search_flow(
                search_query,
                user_name,
                user_location,
                formatted_topics,
                formatted_current_time,
                history_messages,
                session_id=session_id,
            )

        return await cls._execute_direct_flow(
            user_name,
            user_location,
            formatted_topics,
            formatted_current_time,
            history_messages,
            session_id=session_id,
        )
