import re
from typing import Optional, Sequence, Type, TypeVar, cast

from config.settings import settings
from core.observability import langfuse_handler
from langchain_core.messages import BaseMessage, SystemMessage
from langchain_groq import ChatGroq
from pydantic import BaseModel, SecretStr
from utils.logger import logger

T = TypeVar("T", bound=BaseModel)


class LLMFactory:
    _instance: Optional[ChatGroq] = None

    @classmethod
    def get_llm(cls, temperature: Optional[float] = None) -> ChatGroq:
        temp = temperature if temperature is not None else settings.default_temperature
        api_key = SecretStr(settings.groq_api_key) if settings.groq_api_key else None
        return ChatGroq(
            model=settings.groq_model,
            temperature=temp,
            api_key=api_key,
        )


llm = LLMFactory.get_llm()


def extract_json_from_failed_generation(
    error_msg: str, schema_cls: Type[T]
) -> Optional[T]:
    match = re.search(
        r"<function=[^>]+>\s*(\{.*?\})\s*</function>", error_msg, re.DOTALL
    )
    if match:
        try:
            return schema_cls.model_validate_json(match.group(1))
        except Exception:
            pass

    json_match = re.search(r"(\{.*\})", error_msg, re.DOTALL)
    if json_match:
        try:
            return schema_cls.model_validate_json(json_match.group(1))
        except Exception:
            pass
    return None


async def ainvoke_structured(
    llm_instance: ChatGroq,
    schema_cls: Type[T],
    messages: Sequence[BaseMessage],
) -> T:
    try:
        structured_llm = llm_instance.with_structured_output(schema_cls)
        res = await structured_llm.ainvoke(
            messages, config={"callbacks": [langfuse_handler]}
        )
        return cast(T, res)
    except Exception as e:
        err_str = str(e)
        if "tool_use_failed" in err_str or "failed_generation" in err_str:
            recovered = extract_json_from_failed_generation(err_str, schema_cls)
            if recovered is not None:
                logger.info(
                    f"Successfully recovered {schema_cls.__name__} from Groq failed_generation error."
                )
                return recovered

        logger.warning(
            f"Retrying {schema_cls.__name__} with json_mode fallback due to Groq error: {e}"
        )
        json_sys_msg = SystemMessage(
            f"Respond exclusively in JSON format matching the schema for {schema_cls.__name__}."
        )
        json_llm = llm_instance.with_structured_output(schema_cls, method="json_mode")
        res = await json_llm.ainvoke(
            [json_sys_msg] + list(messages), config={"callbacks": [langfuse_handler]}
        )
        return cast(T, res)
