from typing import Annotated, TypedDict

from langgraph.graph.message import add_messages


class ChatState(TypedDict, total=False):
    user_id: str
    name: str
    location: str
    topic_preferences: list[str]
    current_agent: str
    messages: Annotated[list, add_messages]
    engagement_response: str
