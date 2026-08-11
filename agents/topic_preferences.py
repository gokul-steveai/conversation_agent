from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from config.constants import (
    DEFAULT_TOPIC_GREETING_TEMPLATE,
    SYSTEM_PROMPT_TOPIC_PREF_TEMPLATE,
)
from core.llm_factory import llm
from schemas.schemas import TopicPreferencesResponse
from schemas.state import OnboardingState
from utils.console import ConsoleUI


async def topic_preference_agent(state: OnboardingState):
    name = state.get("name", "there")
    location = state.get("location", "")
    current_topics = state.get("topic_preferences", [])

    if current_topics:
        return {"topic_preferences": current_topics}

    structured_llm = llm.with_structured_output(TopicPreferencesResponse)

    greeting = DEFAULT_TOPIC_GREETING_TEMPLATE.format(name=name)
    ConsoleUI.agent_speak(greeting)

    messages = [
        SystemMessage(
            SYSTEM_PROMPT_TOPIC_PREF_TEMPLATE.format(name=name, location=location)
        ),
        AIMessage(greeting),
    ]

    extracted_topics = list(current_topics)

    while True:
        user_input = await ConsoleUI.get_user_input()
        messages.append(HumanMessage(user_input))

        response: TopicPreferencesResponse = await structured_llm.ainvoke(messages)

        if response.topics:
            extracted_topics = response.topics

        if response.is_complete or extracted_topics:
            final_reply = (
                response.agent_response
                or f"Awesome! I've noted down your interest in: {', '.join(extracted_topics)}."
            )
            ConsoleUI.agent_speak(final_reply)
            return {"topic_preferences": extracted_topics}

        ConsoleUI.agent_speak(response.agent_response)
        messages.append(AIMessage(response.agent_response))
