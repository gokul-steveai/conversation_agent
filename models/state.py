from typing import Annotated, TypedDict

from langgraph.graph.message import add_messages


class OnboardingState(TypedDict, total=False):
    name: str
    location: str
    topic_preferences: list[str]
    engagement_response: str
    messages: Annotated[list, add_messages]
    next_node: str
