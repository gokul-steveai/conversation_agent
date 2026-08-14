import re
from typing import Any, List, Union

from pydantic import ValidationError


def sanitize_response(text: Union[str, List[Any]]) -> str:
    if not text:
        return ""

    if isinstance(text, list):
        parts: List[str] = []
        for item in text:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and "text" in item:
                parts.append(str(item["text"]))
            else:
                parts.append(str(item))
        str_text = " ".join(parts)
    else:
        str_text = str(text)

    cleaned = str_text
    leakage_patterns = [
        r"^based on (?:the )?(?:untrusted )?(?:retrieved )?web data,?\s*",
        r"^based on the provided data,?\s*",
        r"note that this information is based on untrusted.*$",
        r"note that the provided data is limited.*$",
        r"as of my knowledge cutoff in \d{4},?\s*",
    ]
    for leak_pat in leakage_patterns:
        cleaned = re.sub(
            leak_pat, "", cleaned, flags=re.IGNORECASE | re.MULTILINE
        ).strip()

    return cleaned if cleaned else str_text.strip()


def format_validation_error(e: ValidationError) -> str:
    """Formats raw Pydantic ValidationError instances into clean, user-friendly bullet points."""
    messages = []
    for err in e.errors():
        loc = err.get("loc", ["Field"])
        field = loc[-1] if loc else "Field"
        msg = err.get("msg", "")
        if "Value error," in msg:
            msg = msg.replace("Value error,", "").strip()
        field_name = str(field).replace("_", " ").title()
        messages.append(f"• **{field_name}**: {msg}")
    return "Please fix the following validation errors:\n" + "\n".join(messages)
