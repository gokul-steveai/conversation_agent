from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple

from core.database import DatabaseManager, get_db
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
from services import MemoryService, SearchService
from utils import sanitize_response

from langfuse import observe


class ChatController:
    _memory_service: Optional[MemoryService] = None

    @classmethod
    def _get_memory_service(cls) -> Optional[MemoryService]:
        if DatabaseManager._SessionLocal:
            if cls._memory_service is None:
                cls._memory_service = MemoryService(get_db)
            return cls._memory_service
        return None

    @classmethod
    async def _save_message_memory(
        cls, session_id: str, content: str, role: str
    ) -> None:
        if not session_id:
            return
        try:
            memory_service = cls._get_memory_service()
            if memory_service:
                await memory_service.write_conversational_memory(
                    content=content, role=role, thread_id=session_id
                )
        except Exception:
            pass

    @classmethod
    async def _save_tool_log(
        cls,
        session_id: str,
        tool_name: str,
        tool_args: Any,
        result: str,
        status: str = "success",
        error_message: Optional[str] = None,
    ) -> None:
        if not session_id:
            return
        try:
            memory_service = cls._get_memory_service()
            if memory_service:
                await memory_service.write_tool_log(
                    thread_id=session_id,
                    tool_name=tool_name,
                    tool_args=tool_args,
                    result=result,
                    status=status,
                    error_message=error_message,
                )
        except Exception:
            pass

    @classmethod
    def _bound_history(
        cls, history_messages: List[BaseMessage], max_recent: int = 12
    ) -> List[BaseMessage]:
        non_system_messages = [
            message
            for message in history_messages
            if not isinstance(message, SystemMessage)
        ]
        return non_system_messages[-max_recent:]

    @classmethod
    async def _update_user_context_from_history(
        cls,
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
                existing_topics_raw = state.get("topic_preferences", [])
                existing_topics: List[str] = (
                    existing_topics_raw if isinstance(existing_topics_raw, list) else []
                )
                new_topics = [
                    topic.strip() for topic in refined.topics if topic.strip()
                ]
                state["topic_preferences"] = list(
                    dict.fromkeys(existing_topics + new_topics)
                )
        except Exception:
            pass

    @classmethod
    @observe(name="evaluate_search_decision", as_type="chain", capture_input=False)
    async def _evaluate_prompt(
        cls,
        user_name: str,
        user_location: str,
        user_text: str,
        history_messages: List[BaseMessage],
    ) -> ChatDecision:
        bounded_history = cls._bound_history(history_messages, max_recent=6)
        system_msg = SystemMessage(
            SYSTEM_PROMPT_SEARCH_EVALUATION.format(
                user_name=user_name,
                user_loc=user_location,
                user_text=user_text,
            )
        )
        evaluation_messages = [system_msg] + bounded_history
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
    @observe(name="execute_search_flow", as_type="chain", capture_input=False)
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
        try:
            retrieved_web_data = await SearchService.asearch_general(search_query)
            await cls._save_tool_log(
                session_id,
                "tavily_search",
                {"query": search_query},
                retrieved_web_data,
                status="success",
            )
        except Exception as e:
            err_msg = str(e)
            retrieved_web_data = f"[Web search failed: {err_msg}]"
            await cls._save_tool_log(
                session_id,
                "tavily_search",
                {"query": search_query},
                result="",
                status="error",
                error_message=err_msg,
            )
            tool_logs.append(
                {
                    "role": "tool",
                    "content": f"⚠️ [Tavily Search Failed] {err_msg}",
                }
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
    @observe(name="execute_direct_flow", as_type="chain")
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
    def _prepare_user_context(
        cls, state: Dict[str, Any]
    ) -> Tuple[str, str, str, str, str]:
        session_id_val = state.get("session_id") or state.get("thread_id") or ""
        session_id = session_id_val if isinstance(session_id_val, str) else ""

        user_name_val = state.get("name") or "User"
        user_name = user_name_val if isinstance(user_name_val, str) else "User"

        user_location_val = state.get("location") or "Not specified"
        user_location = (
            user_location_val if isinstance(user_location_val, str) else "Not specified"
        )

        user_topics_val = state.get("topic_preferences") or []
        user_topics = user_topics_val if isinstance(user_topics_val, list) else []
        formatted_topics = ", ".join(user_topics) if user_topics else "General"
        formatted_current_time = datetime.now(timezone.utc).strftime(
            "%Y-%m-%d %H:%M UTC"
        )
        return (
            session_id,
            user_name,
            user_location,
            formatted_topics,
            formatted_current_time,
        )

    @classmethod
    @observe(name="chat_controller_process_step")
    async def process_step(
        cls,
        user_text: str,
        state: Dict[str, Any],
        history_messages: List[BaseMessage],
    ) -> Tuple[str, List[Dict[str, Any]]]:
        history_messages.append(HumanMessage(user_text))
        await cls._update_user_context_from_history(history_messages, state)

        (
            session_id,
            user_name,
            user_location,
            formatted_topics,
            formatted_current_time,
        ) = cls._prepare_user_context(state)

        await cls._save_message_memory(session_id, user_text, role="user")

        decision = await cls._evaluate_prompt(
            user_name, user_location, user_text, history_messages
        )

        if decision.declared_user_location and decision.declared_user_location.strip():
            user_location = decision.declared_user_location.strip()
            state["location"] = user_location

        if decision.extracted_name and decision.extracted_name.strip():
            user_name = decision.extracted_name.strip()
            state["name"] = user_name

        if decision.extracted_topics:
            existing_topics_raw = state.get("topic_preferences", [])
            existing_topics: List[str] = (
                existing_topics_raw if isinstance(existing_topics_raw, list) else []
            )
            new_topics = [
                topic.strip() for topic in decision.extracted_topics if topic.strip()
            ]
            if new_topics:
                state["topic_preferences"] = list(
                    dict.fromkeys(existing_topics + new_topics)
                )

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

    @classmethod
    async def _stream_and_record_reply(
        cls,
        messages: List[BaseMessage],
        history_messages: List[BaseMessage],
        session_id: str = "",
    ) -> AsyncGenerator[str, None]:
        full_reply_parts = []
        buffered_prefix = ""
        prefix_flushed = False
        MAX_PREFIX_BUFFER_LEN = 120

        async for chunk in llm.astream(
            messages, config={"callbacks": [langfuse_handler]}
        ):
            raw_chunk = chunk.content if hasattr(chunk, "content") else str(chunk)
            if isinstance(raw_chunk, list):
                raw_chunk = " ".join(
                    item.get("text", "") if isinstance(item, dict) else str(item)
                    for item in raw_chunk
                )
            if not raw_chunk:
                continue

            full_reply_parts.append(raw_chunk)

            if not prefix_flushed:
                buffered_prefix += raw_chunk
                if (
                    len(buffered_prefix) >= MAX_PREFIX_BUFFER_LEN
                    or "\n" in buffered_prefix
                ):
                    sanitized_prefix = sanitize_response(buffered_prefix)
                    prefix_flushed = True
                    if sanitized_prefix:
                        yield sanitized_prefix
            else:
                yield raw_chunk

        if not prefix_flushed and buffered_prefix:
            sanitized_prefix = sanitize_response(buffered_prefix)
            if sanitized_prefix:
                yield sanitized_prefix

        full_raw_reply = "".join(full_reply_parts)
        assistant_reply = sanitize_response(full_raw_reply)
        history_messages.append(AIMessage(assistant_reply))
        await cls._save_message_memory(session_id, assistant_reply, role="assistant")

    @classmethod
    @observe(name="chat_controller_process_step_stream")
    async def process_step_stream(
        cls,
        user_text: str,
        state: Dict[str, Any],
        history_messages: List[BaseMessage],
    ) -> AsyncGenerator[Dict[str, Any], None]:
        history_messages.append(HumanMessage(user_text))
        await cls._update_user_context_from_history(history_messages, state)

        (
            session_id,
            user_name,
            user_location,
            formatted_topics,
            formatted_current_time,
        ) = cls._prepare_user_context(state)

        await cls._save_message_memory(session_id, user_text, role="user")

        decision = await cls._evaluate_prompt(
            user_name, user_location, user_text, history_messages
        )

        if decision.declared_user_location and decision.declared_user_location.strip():
            user_location = decision.declared_user_location.strip()
            state["location"] = user_location

        if decision.extracted_name and decision.extracted_name.strip():
            user_name = decision.extracted_name.strip()
            state["name"] = user_name

        if decision.extracted_topics:
            existing_topics_raw = state.get("topic_preferences", [])
            existing_topics: List[str] = (
                existing_topics_raw if isinstance(existing_topics_raw, list) else []
            )
            new_topics = [
                topic.strip() for topic in decision.extracted_topics if topic.strip()
            ]
            if new_topics:
                state["topic_preferences"] = list(
                    dict.fromkeys(existing_topics + new_topics)
                )

        yield {"type": "state", "updated_state": state}

        if decision.needs_clarification and decision.clarification_question:
            clarification_question = decision.clarification_question.strip()
            history_messages.append(AIMessage(clarification_question))
            await cls._save_message_memory(
                session_id, clarification_question, role="assistant"
            )
            yield {"type": "token", "content": clarification_question}
            return

        search_query, is_search_required = cls._refine_search_query(
            decision, user_text, user_location
        )

        if is_search_required:
            tool_msg = f"🔍 [Tavily Search] Autonomously searching live web data: '{search_query}'..."
            yield {"type": "tool", "content": tool_msg}

            try:
                retrieved_web_data = await SearchService.asearch_general(search_query)
                await cls._save_tool_log(
                    session_id,
                    "tavily_search",
                    {"query": search_query},
                    retrieved_web_data,
                    status="success",
                )
            except Exception as e:
                err_msg = str(e)
                retrieved_web_data = f"[Web search failed: {err_msg}]"
                await cls._save_tool_log(
                    session_id,
                    "tavily_search",
                    {"query": search_query},
                    result="",
                    status="error",
                    error_message=err_msg,
                )
                yield {"type": "tool", "content": f"⚠️ [Tavily Search Failed] {err_msg}"}

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
            async for token_chunk in cls._stream_and_record_reply(
                [system_message] + bounded_history + [web_search_message],
                history_messages,
                session_id=session_id,
            ):
                yield {"type": "token", "content": token_chunk}
        else:
            system_message = SystemMessage(
                SYSTEM_PROMPT_DIRECT_CHAT.format(
                    user_name=user_name,
                    user_loc=user_location,
                    topics_str=formatted_topics,
                    current_time_str=formatted_current_time,
                )
            )
            bounded_history = cls._bound_history(history_messages)
            async for token_chunk in cls._stream_and_record_reply(
                [system_message] + bounded_history,
                history_messages,
                session_id=session_id,
            ):
                yield {"type": "token", "content": token_chunk}
