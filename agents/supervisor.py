from langchain_core.messages import SystemMessage

from config.constants import (
    NODE_ENGAGEMENT,
    NODE_FINISH,
    NODE_PERSONAL_INFO,
    NODE_TOPIC_PREF,
)
from core.llm_factory import llm
from schemas.schemas import SupervisorResponse
from schemas.state import OnboardingState


async def supervisor_agent(state: OnboardingState):
    name = state.get("name")
    location = state.get("location")
    topics = state.get("topic_preferences", [])
    engagement = state.get("engagement_response")

    structured_supervisor = llm.with_structured_output(SupervisorResponse)

    prompt = f"""
    You are the Supervisor Orchestrator Agent overseeing customer onboarding.
    
    Current State of Onboarding:
    - Customer Name: {name if name else "NOT GATHERED"}
    - Customer Location: {location if location else "NOT GATHERED"}
    - Topic Preferences: {topics if topics else "NOT GATHERED"}
    - Engagement Completed: {"YES" if engagement else "NO"}

    Routing Logic Rules:
    1. If `name` or `location` are NOT GATHERED, or if the customer indicates they want to change their name/location -> route to `{NODE_PERSONAL_INFO}`.
    2. If `name` and `location` ARE gathered, but `topic_preferences` are NOT GATHERED (or user wants to change interests) -> route to `{NODE_TOPIC_PREF}`.
    3. If `name`, `location`, and `topic_preferences` are ALL gathered, but Engagement is NOT completed -> route to `{NODE_ENGAGEMENT}`.
    4. If all information is gathered AND customer has completed engagement/session -> route to `{NODE_FINISH}`.
    """

    response: SupervisorResponse = await structured_supervisor.ainvoke(
        [SystemMessage(prompt)]
    )

    return {"next_node": response.next_node}
