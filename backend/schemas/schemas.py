from typing import Any, List, Optional

from pydantic import BaseModel, Field, field_validator


class StateUpdate(BaseModel):
    name: Optional[str] = Field(
        default=None,
        description="Most specific, refined customer name confirmed in conversation",
    )
    location: Optional[str] = Field(
        default=None,
        description="Most specific, refined city or location explicitly declared by user in conversation.",
    )
    topics: Optional[List[str]] = Field(
        default_factory=list,
        description="List of topics/interests identified in conversation. Must be a JSON array of strings (e.g. ['AI', 'tech']), or [] if none.",
    )

    @field_validator("topics", mode="before")
    @classmethod
    def _coerce_null_topics(cls, v: Any) -> List[str]:
        if v is None:
            return []
        if isinstance(v, str):
            return [t.strip() for t in v.split(",") if t.strip()]
        if isinstance(v, list):
            return [str(item).strip() for item in v if str(item).strip()]
        return []


class ChatDecision(BaseModel):
    needs_clarification: bool = Field(
        default=False,
        description="True ONLY if an actionable parameter-dependent request is missing mandatory parameters (e.g. asking for local weather when location is 'Not specified' and no city is provided). NEVER set True for general, historical, educational, or conversational questions.",
    )
    clarification_question: Optional[str] = Field(
        default=None,
        description="The polite, friendly clarification question to ask the user ONLY if essential location/action parameters are missing.",
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
    extracted_topics: Optional[List[str]] = Field(
        default_factory=list,
        description="List of topics/interests mentioned in prompt if any. Must be a JSON array of strings (e.g. ['AI', 'tech']), or [] if none.",
    )

    @field_validator("extracted_topics", mode="before")
    @classmethod
    def _coerce_null_extracted_topics(cls, v: Any) -> List[str]:
        if v is None:
            return []
        if isinstance(v, str):
            return [t.strip() for t in v.split(",") if t.strip()]
        if isinstance(v, list):
            return [str(item).strip() for item in v if str(item).strip()]
        return []

    @field_validator("needs_clarification", "needs_web_search", mode="before")
    @classmethod
    def _coerce_null_bool(cls, v: Any) -> bool:
        if v is None:
            return False
        if isinstance(v, str):
            return v.lower() in ("true", "1", "yes")
        return bool(v)


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
