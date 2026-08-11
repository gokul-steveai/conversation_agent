from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from config.constants import EXIT_KEYWORDS, SYSTEM_PROMPT_ENGAGEMENT_TEMPLATE
from core.llm_factory import llm
from schemas.state import OnboardingState
from services.profile_service import ProfileService
from services.search_service import SearchService
from utils.console import ConsoleUI


async def customer_engagement_agent(state: OnboardingState):
    name = state.get("name", "Friend")
    location = state.get("location", "Unknown")
    topics = state.get("topic_preferences", [])

    ConsoleUI.print_tool_call(
        "TavilySearch", f"Searching live facts for location: '{location}'"
    )
    location_info = SearchService.search_location_facts(location)

    ConsoleUI.print_tool_call(
        "TavilySearch", f"Searching trending news for topics: {topics}"
    )
    news_info = SearchService.search_topic_news(topics, location)

    ConsoleUI.print_tool_call("ProfileService", "Persisting user profile data...")
    ProfileService.save_profile(name, location, topics)

    system_prompt = SystemMessage(
        SYSTEM_PROMPT_ENGAGEMENT_TEMPLATE.format(
            name=name,
            location=location,
            location_info=location_info,
            news_info=news_info,
        )
    )

    initial_response = await llm.ainvoke(
        [
            system_prompt,
            HumanMessage("Generate my welcome story with real-time news & facts!"),
        ]
    )
    ConsoleUI.agent_speak(initial_response.content)

    ConsoleUI.agent_speak(
        "Feel free to ask me any follow-up question, or press Enter / type 'done' to finish onboarding!"
    )
    user_input = await ConsoleUI.get_user_input()

    if user_input.strip() and user_input.strip().lower() not in EXIT_KEYWORDS:
        messages = [
            system_prompt,
            AIMessage(initial_response.content),
            HumanMessage(user_input),
        ]
        followup = await llm.ainvoke(messages)
        ConsoleUI.agent_speak(followup.content)

    return {"engagement_response": initial_response.content}
