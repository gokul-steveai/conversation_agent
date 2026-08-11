from utils.logger import logger


class ProfileService:
    @staticmethod
    def save_profile(name: str, location: str, topics: list[str]) -> bool:
        """Persists customer profile data."""
        logger.info(
            f"Persisting profile data: Name='{name}', Location='{location}', Topics={topics}"
        )
        return True
