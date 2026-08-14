from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple

from core.llm_factory import llm
from core.observability import langfuse_handler
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from prompts import (
    HUMAN_PROMPT_UNTRUSTED_WEB_DATA,
    SYSTEM_PROMPT_DIRECT_CHAT,
    SYSTEM_PROMPT_WEB_SYNTHESIS,
)
from services import MemoryService, SearchService
from utils.chat_utils import (
    bound_history,
    evaluate_search_prompt,
    merge_state_topics,
    prepare_user_context,
    refine_search_query,
    update_user_context_from_history,
)
from utils.logger import logger
from utils.sanitizer import StreamSanitizer, sanitize_response

from langfuse import observe


class ChatController:
    def __init__(self, memory_service: MemoryService) -> None:
        self._memory_service = memory_service

    async def _save_message_memory(
        self, session_id: str, content: str, role: str
    ) -> None:
        if not session_id:
            return
        try:
            await self._memory_service.write_conversational_memory(
                content=content, role=role, thread_id=session_id
            )
        except Exception as e:
            logger.error(f"Error saving {role} memory to DB: {e}")

    async def _save_tool_log(
        self,
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
            await self._memory_service.write_tool_log(
                thread_id=session_id,
                tool_name=tool_name,
                tool_args=tool_args,
                result=result,
                status=status,
                error_message=error_message,
            )
        except Exception as e:
            logger.error(f"Error saving tool log to DB: {e}")

    async def _invoke_and_record_reply(
        self,
        messages: List[BaseMessage],
        history_messages: List[BaseMessage],
        session_id: str = "",
    ) -> str:
        llm_response = await llm.ainvoke(
            messages, config={"callbacks": [langfuse_handler]}
        )
        assistant_reply = sanitize_response(llm_response.content)
        history_messages.append(AIMessage(assistant_reply))
        await self._save_message_memory(session_id, assistant_reply, role="assistant")
        return assistant_reply

    @observe(name="execute_search_flow", as_type="chain", capture_input=False)
    async def _execute_search_flow(
        self,
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
            await self._save_tool_log(
                session_id,
                "tavily_search",
                {"query": search_query},
                retrieved_web_data,
                status="success",
            )
        except Exception as e:
            err_msg = str(e)
            retrieved_web_data = f"[Web search failed: {err_msg}]"
            await self._save_tool_log(
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
        bounded = bound_history(history_messages)
        assistant_reply = await self._invoke_and_record_reply(
            [system_message] + bounded + [web_search_message],
            history_messages,
            session_id=session_id,
        )
        return assistant_reply, tool_logs

    @observe(name="execute_direct_flow", as_type="chain")
    async def _execute_direct_flow(
        self,
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
        bounded = bound_history(history_messages)
        assistant_reply = await self._invoke_and_record_reply(
            [system_message] + bounded,
            history_messages,
            session_id=session_id,
        )
        return assistant_reply, []

    async def _stream_and_record_reply(
        self,
        messages: List[BaseMessage],
        history_messages: List[BaseMessage],
        session_id: str = "",
    ) -> AsyncGenerator[str, None]:
        full_reply_parts = []
        sanitizer = StreamSanitizer(window_size=150)

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

            emitted = sanitizer.process_chunk(raw_chunk)
            if emitted:
                yield emitted

        final_flush = sanitizer.flush()
        if final_flush:
            yield final_flush

        full_raw_reply = "".join(full_reply_parts)
        assistant_reply = sanitize_response(full_raw_reply)
        history_messages.append(AIMessage(assistant_reply))
        await self._save_message_memory(session_id, assistant_reply, role="assistant")

    @observe(name="chat_controller_process_step")
    async def process_step(
        self,
        user_text: str,
        state: Dict[str, Any],
        history_messages: List[BaseMessage],
    ) -> Tuple[str, List[Dict[str, Any]]]:
        history_messages.append(HumanMessage(user_text))
        await update_user_context_from_history(history_messages, state)

        (
            session_id,
            user_name,
            user_location,
            formatted_topics,
            formatted_current_time,
        ) = prepare_user_context(state)

        await self._save_message_memory(session_id, user_text, role="user")

        decision = await evaluate_search_prompt(
            user_name, user_location, user_text, history_messages
        )

        if decision.declared_user_location and decision.declared_user_location.strip():
            user_location = decision.declared_user_location.strip()
            state["location"] = user_location

        if decision.extracted_name and decision.extracted_name.strip():
            user_name = decision.extracted_name.strip()
            state["name"] = user_name

        if decision.extracted_topics:
            merge_state_topics(state, decision.extracted_topics)

        if decision.needs_clarification and decision.clarification_question:
            clarification_question = decision.clarification_question.strip()
            history_messages.append(AIMessage(clarification_question))
            await self._save_message_memory(
                session_id, clarification_question, role="assistant"
            )
            return clarification_question, []

        search_query, is_search_required = refine_search_query(
            decision, user_text, user_location
        )

        if is_search_required:
            return await self._execute_search_flow(
                search_query,
                user_name,
                user_location,
                formatted_topics,
                formatted_current_time,
                history_messages,
                session_id=session_id,
            )

        return await self._execute_direct_flow(
            user_name,
            user_location,
            formatted_topics,
            formatted_current_time,
            history_messages,
            session_id=session_id,
        )

    @observe(name="chat_controller_process_step_stream")
    async def process_step_stream(
        self,
        user_text: str,
        state: Dict[str, Any],
        history_messages: List[BaseMessage],
    ) -> AsyncGenerator[Dict[str, Any], None]:
        history_messages.append(HumanMessage(user_text))
        await update_user_context_from_history(history_messages, state)

        (
            session_id,
            user_name,
            user_location,
            formatted_topics,
            formatted_current_time,
        ) = prepare_user_context(state)

        await self._save_message_memory(session_id, user_text, role="user")

        decision = await evaluate_search_prompt(
            user_name, user_location, user_text, history_messages
        )

        if decision.declared_user_location and decision.declared_user_location.strip():
            user_location = decision.declared_user_location.strip()
            state["location"] = user_location

        if decision.extracted_name and decision.extracted_name.strip():
            user_name = decision.extracted_name.strip()
            state["name"] = user_name

        if decision.extracted_topics:
            merge_state_topics(state, decision.extracted_topics)

        yield {"type": "state", "updated_state": state}

        if decision.needs_clarification and decision.clarification_question:
            clarification_question = decision.clarification_question.strip()
            history_messages.append(AIMessage(clarification_question))
            await self._save_message_memory(
                session_id, clarification_question, role="assistant"
            )
            yield {"type": "token", "content": clarification_question}
            return

        search_query, is_search_required = refine_search_query(
            decision, user_text, user_location
        )

        if is_search_required:
            tool_msg = f"🔍 [Tavily Search] Autonomously searching live web data: '{search_query}'..."
            yield {"type": "tool", "content": tool_msg}

            try:
                retrieved_web_data = await SearchService.asearch_general(search_query)
                await self._save_tool_log(
                    session_id,
                    "tavily_search",
                    {"query": search_query},
                    retrieved_web_data,
                    status="success",
                )
            except Exception as e:
                err_msg = str(e)
                retrieved_web_data = f"[Web search failed: {err_msg}]"
                await self._save_tool_log(
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
            bounded = bound_history(history_messages)
            async for token_chunk in self._stream_and_record_reply(
                [system_message] + bounded + [web_search_message],
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
            bounded = bound_history(history_messages)
            async for token_chunk in self._stream_and_record_reply(
                [system_message] + bounded,
                history_messages,
                session_id=session_id,
            ):
                yield {"type": "token", "content": token_chunk}
