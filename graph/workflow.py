from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from agents import (
    customer_engagement_agent,
    personal_information_agent,
    supervisor_agent,
    topic_preference_agent,
)
from config.constants import (
    NODE_ENGAGEMENT,
    NODE_PERSONAL_INFO,
    NODE_SUPERVISOR,
    NODE_TOPIC_PREF,
)
from graph.router import route_supervisor
from schemas.state import OnboardingState


def build_graph() -> CompiledStateGraph[
    OnboardingState, Any, OnboardingState, OnboardingState
]:
    builder = StateGraph(OnboardingState)

    builder.add_node(NODE_SUPERVISOR, supervisor_agent)
    builder.add_node(NODE_PERSONAL_INFO, personal_information_agent)
    builder.add_node(NODE_TOPIC_PREF, topic_preference_agent)
    builder.add_node(NODE_ENGAGEMENT, customer_engagement_agent)

    builder.add_edge(START, NODE_SUPERVISOR)

    builder.add_conditional_edges(
        NODE_SUPERVISOR,
        route_supervisor,
        {
            NODE_PERSONAL_INFO: NODE_PERSONAL_INFO,
            NODE_TOPIC_PREF: NODE_TOPIC_PREF,
            NODE_ENGAGEMENT: NODE_ENGAGEMENT,
            END: END,
        },
    )

    builder.add_edge(NODE_PERSONAL_INFO, NODE_SUPERVISOR)
    builder.add_edge(NODE_TOPIC_PREF, NODE_SUPERVISOR)
    builder.add_edge(NODE_ENGAGEMENT, NODE_SUPERVISOR)

    return builder.compile()


graph = build_graph()

try:
    graph.get_graph().draw_mermaid_png(output_file_path="onboarding.png")
except Exception:
    try:
        graph.get_graph().draw_png(output_file_path="onboarding.png")
    except Exception:
        pass
