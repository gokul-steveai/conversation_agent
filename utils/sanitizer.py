import re


def sanitize_response(text: str) -> str:
    if not text:
        return ""
    pattern = r"\b(?:topics|is_complete|name|location|next_node|reason)\s*=\s*.*$"
    cleaned = re.sub(pattern, "", text, flags=re.IGNORECASE | re.MULTILINE).strip()
    return cleaned if cleaned else text.strip()
