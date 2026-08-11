import re

from pydantic import ValidationError


def sanitize_response(text: str) -> str:
    if not text:
        return ""
    pattern = r"\b(?:topics|is_complete|name|location|next_node|reason)\s*=\s*.*$"
    cleaned = re.sub(pattern, "", text, flags=re.IGNORECASE | re.MULTILINE).strip()
    return cleaned if cleaned else text.strip()


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
