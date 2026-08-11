from langchain_core.tools import tool

from services.profile_service import ProfileService
from services.search_service import SearchService


@tool
def search_web_information(query: str) -> str:
    """Performs a live web search using Tavily API to retrieve real-time news, current events, local facts, history, weather, or detailed information.

    Use this tool whenever:
    - The customer asks questions requiring real-time, live, or up-to-date facts (e.g. news, events, local landmarks, places to visit).
    - The customer requests more details about a city, history, culture, sports, or technology that you need to search on the web.
    - You need external web verification or additional context to answer the user's question accurately.

    Args:
        query: The specific web search query string (e.g. 'latest tech events in Bhopal', 'famous places in Dhar').
    """
    return SearchService.search_location_facts(query)


def search_location_facts(location: str) -> str:
    """Searches Tavily for interesting real-time facts, landmarks, and highlights about a location."""
    return SearchService.search_location_facts(location)


def search_topic_news(topics: list[str], location: str = "") -> str:
    """Searches Tavily for current news and trending stories on specific topics."""
    return SearchService.search_topic_news(topics, location)


def save_user_profile(name: str, location: str, topics: list[str]) -> str:
    """Persists user profile data."""
    ProfileService.save_profile(name, location, topics)
    return f"Profile successfully saved for {name} from {location}."
