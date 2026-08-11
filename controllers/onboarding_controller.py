from typing import Any, Dict, Tuple

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from config.constants import (
    DEFAULT_TOPIC_GREETING_TEMPLATE,
    NODE_ENGAGEMENT,
    NODE_PERSONAL_INFO,
    NODE_TOPIC_PREF,
    SYSTEM_PROMPT_ENGAGEMENT_TEMPLATE,
    SYSTEM_PROMPT_TOPIC_PREF_TEMPLATE,
)
from core.llm_factory import llm
from models.schemas import (
    PersonalInformationResponse,
    StateUpdate,
    TopicPreferencesResponse,
    WebSearchDecision,
)
from services.profile_service import ProfileService
from services.search_service import SearchService
from tools.tavily_search import search_web_information
from utils.sanitizer import sanitize_response


class OnboardingController:
    @classmethod
    async def _sync_state_refinement(
        cls, history_messages: list, state: Dict[str, Any]
    ) -> None:
        """Autonomously extracts and updates state details (Name, Location, Topics) from conversation history."""
        try:
            state_extractor = llm.with_structured_output(StateUpdate)
            refined: StateUpdate = await state_extractor.ainvoke(history_messages)

            if refined.name and refined.name.strip():
                state["name"] = refined.name.strip()

            if refined.location and refined.location.strip():
                state["location"] = refined.location.strip()

            if refined.topics:
                existing = state.get("topic_preferences", [])
                merged = list(
                    dict.fromkeys(
                        existing + [t.strip() for t in refined.topics if t.strip()]
                    )
                )
                state["topic_preferences"] = merged

            if state.get("name") and state.get("location"):
                ProfileService.save_profile(
                    state["name"], state["location"], state.get("topic_preferences", [])
                )
        except Exception:
            pass

    @classmethod
    async def process_step(
        cls,
        user_text: str,
        state: Dict[str, Any],
        history_messages: list,
    ) -> Tuple[str, list]:
        current_agent = state.get("current_agent", NODE_PERSONAL_INFO)
        history_messages.append(HumanMessage(user_text))
        tool_logs = []

        if current_agent == NODE_PERSONAL_INFO:
            structured_llm = llm.with_structured_output(PersonalInformationResponse)
            response: PersonalInformationResponse = await structured_llm.ainvoke(
                history_messages
            )

            if response.name:
                state["name"] = response.name
            if response.location:
                state["location"] = response.location

            if response.is_complete or (state["name"] and state["location"]):
                raw_reply = (
                    response.agent_response
                    or f"Great to meet you, {state['name']} from {state['location']}!"
                )
                reply = sanitize_response(raw_reply)
                state["current_agent"] = NODE_TOPIC_PREF

                topic_greeting = "\n\n" + DEFAULT_TOPIC_GREETING_TEMPLATE.format(
                    name=state["name"]
                )
                reply += topic_greeting

                history_messages.clear()
                history_messages.extend(
                    [
                        SystemMessage(
                            SYSTEM_PROMPT_TOPIC_PREF_TEMPLATE.format(
                                name=state["name"], location=state["location"]
                            )
                        ),
                        AIMessage(reply),
                    ]
                )
            else:
                reply = sanitize_response(response.agent_response)
                history_messages.append(AIMessage(reply))

            return reply, tool_logs

        elif current_agent == NODE_TOPIC_PREF:
            structured_llm = llm.with_structured_output(TopicPreferencesResponse)
            response: TopicPreferencesResponse = await structured_llm.ainvoke(
                history_messages
            )

            await cls._sync_state_refinement(history_messages, state)

            if response.topics:
                state["topic_preferences"] = response.topics

            if response.is_complete or state["topic_preferences"]:
                state["current_agent"] = NODE_ENGAGEMENT

                tool_logs.append(
                    {
                        "role": "tool",
                        "content": f"🔍 [Tavily Search] Executing live search for facts about '{state['location']}'...",
                    }
                )
                loc_facts = SearchService.search_location_facts(state["location"])

                tool_logs.append(
                    {
                        "role": "tool",
                        "content": f"🔍 [Tavily Search] Executing live news search for topics: {state['topic_preferences']}...",
                    }
                )
                topic_news = SearchService.search_topic_news(
                    state["topic_preferences"], state["location"]
                )

                tool_logs.append(
                    {
                        "role": "tool",
                        "content": f"💾 [Profile Service] Persisting user profile for {state['name']} from {state['location']}...",
                    }
                )
                ProfileService.save_profile(
                    state["name"], state["location"], state["topic_preferences"]
                )

                sys_prompt = SystemMessage(
                    SYSTEM_PROMPT_ENGAGEMENT_TEMPLATE.format(
                        name=state["name"],
                        location=state["location"],
                        location_info=loc_facts,
                        news_info=topic_news,
                    )
                )
                eng_res = await llm.ainvoke(
                    [sys_prompt, HumanMessage("Generate welcome story!")]
                )

                ack_text = f"Awesome! I've taken note of your interest in: {', '.join(state['topic_preferences'])}."
                reply = f"{ack_text}\n\n{sanitize_response(eng_res.content)}"
                state["engagement_response"] = eng_res.content
            else:
                reply = sanitize_response(response.agent_response)
                history_messages.append(AIMessage(reply))

            return reply, tool_logs

        elif current_agent == NODE_ENGAGEMENT:
            await cls._sync_state_refinement(history_messages, state)

            loc = state.get("location", "")
            topics = state.get("topic_preferences", [])
            topics_str = ", ".join(topics) if topics else ""

            search_evaluator = llm.with_structured_output(WebSearchDecision)
            decision: WebSearchDecision = await search_evaluator.ainvoke(
                [
                    SystemMessage(
                        f"You are evaluating if customer '{state.get('name')}' (from '{loc}') needs a live web search to answer their prompt.\n"
                        f"Customer prompt: '{user_text}'"
                    )
                ]
            )

            if decision.needs_web_search and decision.search_query:
                query_str = decision.search_query.strip()
                tool_logs.append(
                    {
                        "role": "tool",
                        "content": f"🔍 [Tavily Search] Agent autonomously executing web search: '{query_str}'...",
                    }
                )
                search_data = search_web_information.invoke({"query": query_str})

                synthesis_prompt = SystemMessage(
                    f"You are an enthusiastic customer engagement agent talking to '{state.get('name')}' from '{loc}'.\n"
                    f"Customer Interests: {topics_str}.\n"
                    f"Live Web Search Results for '{query_str}':\n{search_data}\n\n"
                    "Synthesize a warm, detailed, accurate response directly based on the search results."
                )
                res = await llm.ainvoke([synthesis_prompt] + history_messages)
                clean_reply = sanitize_response(res.content)
                history_messages.append(AIMessage(clean_reply))
                return clean_reply, tool_logs

            sys_prompt = SystemMessage(
                f"You are an enthusiastic customer engagement agent talking to '{state.get('name')}' from '{loc}'.\n"
                f"Customer Interests: {topics_str}.\n"
                "Answer any follow-up questions warmly and concisely."
            )
            res = await llm.ainvoke([sys_prompt] + history_messages)
            clean_reply = sanitize_response(res.content)
            history_messages.append(AIMessage(clean_reply))
            return clean_reply, tool_logs

        return "Session completed.", tool_logs
