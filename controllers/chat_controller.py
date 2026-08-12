from datetime import datetime, timezone
from typing import Any, Dict, Tuple

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from core.llm_factory import ainvoke_structured, llm
from prompts import (
    HUMAN_PROMPT_UNTRUSTED_WEB_DATA,
    SYSTEM_PROMPT_DIRECT_CHAT,
    SYSTEM_PROMPT_SEARCH_EVALUATION,
    SYSTEM_PROMPT_WEB_SYNTHESIS,
)
from schemas.schemas import ChatDecision, StateUpdate
from services.profile_service import ProfileService
from services.search_service import SearchService
from utils.sanitizer import sanitize_response


class ChatController:
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

            if state.get("name") and state.get("location"):
                ProfileService.save_profile(
                    state["name"], state["location"], state.get("topic_preferences", [])
                )
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
    async def _execute_search_flow(
        cls,
        search_query: str,
        user_name: str,
        user_loc: str,
        topics_str: str,
        time_str: str,
        history_messages: list,
    ) -> Tuple[str, list]:
        tool_logs = [
            {
                "role": "tool",
                "content": f"🔍 [Tavily Search] Autonomously searching live web data: '{search_query}'...",
            }
        ]
        web_data = await SearchService.asearch_general(search_query)

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
        res = await llm.ainvoke([sys_msg] + bounded_history + [web_msg])
        reply = sanitize_response(res.content)
        history_messages.append(AIMessage(reply))
        return reply, tool_logs

    @classmethod
    async def _execute_direct_flow(
        cls,
        user_name: str,
        user_loc: str,
        topics_str: str,
        time_str: str,
        history_messages: list,
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
        res = await llm.ainvoke([sys_msg] + bounded_history)
        reply = sanitize_response(res.content)
        history_messages.append(AIMessage(reply))
        return reply, []

    @classmethod
    async def process_step(
        cls,
        user_text: str,
        state: Dict[str, Any],
        history_messages: list,
    ) -> Tuple[str, list]:
        history_messages.append(HumanMessage(user_text))
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
            return clarification, []

        query, is_search = cls._refine_search_query(decision, user_text, user_loc)

        if is_search:
            return await cls._execute_search_flow(
                query, user_name, user_loc, topics_str, time_str, history_messages
            )

        return await cls._execute_direct_flow(
            user_name, user_loc, topics_str, time_str, history_messages
        )
