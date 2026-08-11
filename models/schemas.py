from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class SupervisorResponse(BaseModel):
    next_node: Literal[
        "personal_information", "topic_preferences", "customer_engagement", "FINISH"
    ] = Field(
        description="The next specialized agent node to execute based on current state and user intent"
    )
    reason: str = Field(description="Explanation for why this route was selected")


class PersonalInformationResponse(BaseModel):
    name: Optional[str] = Field(
        default=None, description="Customer's name if identified from conversation"
    )
    location: Optional[str] = Field(
        default=None, description="Customer's location if identified from conversation"
    )
    is_complete: bool = Field(
        description="True ONLY if BOTH name and location are successfully identified"
    )
    agent_response: str = Field(
        description="Friendly, natural response to print to the customer, answering their questions or asking for missing info"
    )


class TopicPreferencesResponse(BaseModel):
    topics: List[str] = Field(
        default_factory=list, description="Topics/interests extracted from conversation"
    )
    is_complete: bool = Field(
        description="True if customer has specified at least one interest or topic"
    )
    agent_response: str = Field(
        description="Friendly response to print to the customer acknowledging their choices or suggesting categories"
    )


class PersonalInformation(BaseModel):
    name: str = Field(description="Customer's name")
    location: str = Field(description="Customer's location")


class TopicPreferences(BaseModel):
    topics: list[str] = Field(description="Topics the customer is interested in")


class StateUpdate(BaseModel):
    name: Optional[str] = Field(
        default=None,
        description="Most specific, refined customer name confirmed in conversation",
    )
    location: Optional[str] = Field(
        default=None,
        description="Most specific, refined city or location confirmed in conversation. If a vague nickname like 'city of lakes' was later clarified or confirmed to be 'Bhopal', extract the refined city name 'Bhopal'.",
    )
    topics: List[str] = Field(
        default_factory=list,
        description="All topics/interests identified or confirmed in conversation",
    )
