from services.profile_service import ProfileService
from services.search_service import SearchService


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
