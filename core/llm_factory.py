from typing import Optional

from langchain_groq import ChatGroq

from config.settings import settings


class LLMFactory:
    _instance: Optional[ChatGroq] = None

    @classmethod
    def get_llm(cls, temperature: Optional[float] = None) -> ChatGroq:
        temp = temperature if temperature is not None else settings.default_temperature
        return ChatGroq(
            model=settings.groq_model,
            temperature=temp,
            groq_api_key=settings.groq_api_key or None,
        )


llm = LLMFactory.get_llm()
