from langgraph.graph import END

from config.constants import NODE_ENGAGEMENT, NODE_PERSONAL_INFO, NODE_TOPIC_PREF
from schemas.state import OnboardingState


def route_supervisor(state: OnboardingState) -> str:
    """Evaluates next_node from state to determine routing destination."""
    next_node = state.get("next_node")
    if next_node in [NODE_PERSONAL_INFO, NODE_TOPIC_PREF, NODE_ENGAGEMENT]:
        return next_node
    return END
