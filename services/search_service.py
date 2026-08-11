from tavily import TavilyClient

from config.settings import settings
from utils.logger import logger


class SearchService:
    @staticmethod
    def _get_client():
        if settings.tavily_api_key:
            return TavilyClient(api_key=settings.tavily_api_key)
        return None

    @classmethod
    def search_location_facts(cls, location: str) -> str:
        """Searches Tavily for real-time facts, landmarks, and highlights of a location."""
        client = cls._get_client()
        if not client:
            logger.info("Tavily API key not provided. Using fallback location data.")
            return f"{location} is a notable destination known for its culture, landmarks, and history."

        try:
            logger.info(f"Executing Tavily Web Search for location facts: {location}")
            query = (
                f"famous landmarks interesting facts history highlights of {location}"
            )
            response = client.search(query=query, max_results=3)
            results = [
                r.get("content", "")
                for r in response.get("results", [])
                if r.get("content")
            ]
            return "\n\n".join(results) if results else f"Highlights of {location}."
        except Exception as e:
            logger.error(f"Tavily location search error: {e}")
            return f"Information about {location}."

    @classmethod
    def search_topic_news(cls, topics: list[str], location: str = "") -> str:
        """Searches Tavily for live news and trending stories on specific topics."""
        client = cls._get_client()
        topics_str = ", ".join(topics) if topics else "general news"
        if not client:
            logger.info("Tavily API key not provided. Using fallback topic news data.")
            return f"Recent developments in {topics_str}."

        try:
            logger.info(f"Executing Tavily Web Search for topic news: {topics_str}")
            query = (
                f"latest news developments trends in {topics_str} {location}".strip()
            )
            response = client.search(query=query, max_results=3)
            results = [
                f"• {r.get('title', 'News')}: {r.get('content', '')}"
                for r in response.get("results", [])
                if r.get("content")
            ]
            return (
                "\n\n".join(results) if results else f"Latest updates on {topics_str}."
            )
        except Exception as e:
            logger.error(f"Tavily topic news search error: {e}")
            return f"Trending news in {topics_str}."
