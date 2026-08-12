from typing import List, Optional

from pydantic import BaseModel, Field


class StateUpdate(BaseModel):
    name: Optional[str] = Field(
        default=None,
        description="Most specific, refined customer name confirmed in conversation",
    )
    location: Optional[str] = Field(
        default=None,
        description="Most specific, refined city or location explicitly declared by user in conversation.",
    )
    topics: List[str] = Field(
        default_factory=list,
        description="All topics/interests identified or confirmed in conversation",
    )


class ChatDecision(BaseModel):
    needs_clarification: bool = Field(
        default=False,
        description="True if the user prompt is missing essential context or parameters (e.g. location for local weather/news when location is missing, dates, specific entity) required to answer accurately.",
    )
    clarification_question: Optional[str] = Field(
        default=None,
        description="The polite, friendly clarification question to ask the user if essential context is missing.",
    )
    needs_web_search: bool = Field(
        default=False,
        description="True if prompt needs real-time web search for facts, news, weather, or current events",
    )
    search_query: Optional[str] = Field(
        default=None, description="The refined query string for Tavily search if needed"
    )
    extracted_name: Optional[str] = Field(
        default=None, description="User name mentioned in prompt if any"
    )
    query_location: Optional[str] = Field(
        default=None,
        description="Target location requested for search/weather/news query (e.g., 'Tokyo' in 'weather in Tokyo')",
    )
    declared_user_location: Optional[str] = Field(
        default=None,
        description="User home/current location explicitly declared by user (e.g., 'I live in Paris', 'My location is London')",
    )
    extracted_topics: List[str] = Field(
        default_factory=list, description="Topics/interests mentioned in prompt if any"
    )


class ChatMessageRequest(BaseModel):
    user_text: str = Field(description="The input text message from user")
    session_id: str = Field(description="Active session ID")
    state: dict = Field(default_factory=dict, description="Current chat state dict")


class ToolLogItem(BaseModel):
    role: str = Field(default="tool")
    content: str = Field(description="Log message string")


class ChatMessageResponse(BaseModel):
    reply: str = Field(description="AI Assistant response reply")
    tool_logs: List[ToolLogItem] = Field(
        default_factory=list, description="Tool execution log messages"
    )
    updated_state: dict = Field(description="Updated session state dict")
