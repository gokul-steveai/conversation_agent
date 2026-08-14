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
        # System disclaimers & pipeline leakage
        r"^based on (?:the )?(?:untrusted )?(?:retrieved )?(?:live )?web data,?\s*",
        r"^based on the provided data,?\s*",
        r"note that this information is based on untrusted.*$",
        r"note that the provided data is limited.*$",
        r"as of my knowledge cutoff in \d{4},?\s*",
        # Social media & website CTA boilerplates
        r"(?:don't|do not) forget to (?:like|share|subscribe)[^\n\.]*[\n\.]?",
        r"subscribe (?:to|for) (?:daily|more|our)[^\n\.]*[\n\.]?",
        r"catch (?:all )?(?:the )?live updates[^\n\.]*on our platform[^\n\.]*[\n\.]?",
        r"keep an eye on our (?:platform|channel)[^\n\.]*[\n\.]?",
        r"click (?:the link|here) (?:below|to subscribe)[^\n\.]*[\n\.]?",
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
