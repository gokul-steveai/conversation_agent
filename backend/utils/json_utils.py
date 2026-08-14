import json
import re
from typing import Any, Dict, Optional, Type, TypeVar

from pydantic import BaseModel
from utils.logger import logger

T = TypeVar("T", bound=BaseModel)


def extract_json_from_failed_generation(
    error_msg: str, schema_cls: Type[T]
) -> Optional[T]:
    """Recovers and validates a Pydantic model instance from raw LLM error payloads or malformed JSON output."""
    if not error_msg:
        return None

    raw_json_str: Optional[str] = None
    match = re.search(
        r"<function=[^>]+>\s*(\{.*?\})\s*</function>", error_msg, re.DOTALL
    )
    if match:
        raw_json_str = match.group(1)
    else:
        fg_match = re.search(
            r"'failed_generation':\s*['\"](\{.*?\})['\"]\s*\}", error_msg, re.DOTALL
        )
        if fg_match:
            raw_json_str = fg_match.group(1)
        else:
            fg_broad = re.search(
                r"'failed_generation':\s*['\"](.*)", error_msg, re.DOTALL
            )
            if fg_broad:
                raw_json_str = fg_broad.group(1)
            else:
                json_match = re.search(r"(\{.*\})", error_msg, re.DOTALL)
                if json_match:
                    raw_json_str = json_match.group(1)

    if raw_json_str:
        # Normalize Python literals and triple-quote blocks to valid JSON
        sanitized = re.sub(r'"""(.*?)"""', r'"\1"', raw_json_str, flags=re.DOTALL)
        sanitized = re.sub(r"\bFalse\b", "false", sanitized)
        sanitized = re.sub(r"\bTrue\b", "true", sanitized)
        sanitized = re.sub(r"\bNone\b", "null", sanitized)

        try:
            return schema_cls.model_validate_json(sanitized)
        except Exception:
            pass

        try:
            clean_json = re.sub(r'\\"', '"', sanitized)
            parsed = json.loads(clean_json)
            if isinstance(parsed, dict):
                valid_fields = schema_cls.model_fields.keys()
                filtered = {k: v for k, v in parsed.items() if k in valid_fields}
                return schema_cls.model_validate(filtered)
        except Exception:
            pass

    # Fallback to schema field extraction via regex when structural JSON parsing fails
    try:
        extracted_data: Dict[str, Any] = {}
        for field_name, field_info in schema_cls.model_fields.items():
            annotation_str = str(field_info.annotation)

            if (
                field_info.annotation in (bool, Optional[bool])
                or "bool" in annotation_str.lower()
            ):
                bool_match = re.search(
                    rf'"{field_name}"\s*:\s*(true|false|True|False)',
                    error_msg,
                    re.IGNORECASE,
                )
                if bool_match:
                    extracted_data[field_name] = bool_match.group(1).lower() == "true"
            elif "List" in annotation_str or "list" in annotation_str:
                list_match = re.search(
                    rf'"{field_name}"\s*:\s*(\[[^\]]*\])', error_msg, re.DOTALL
                )
                if list_match:
                    try:
                        list_str = list_match.group(1).replace("'", '"')
                        extracted_data[field_name] = json.loads(list_str)
                    except Exception:
                        pass
            else:
                str_match = re.search(rf'"{field_name}"\s*:\s*"([^"]+)"', error_msg)
                if str_match:
                    extracted_data[field_name] = str_match.group(1)

        if extracted_data:
            return schema_cls.model_validate(extracted_data)
    except Exception as e:
        logger.debug(f"Field extraction fallback error: {e}")

    return None
