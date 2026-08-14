from typing import Any, Dict

MODEL_TOKEN_LIMITS = {"llama-3.3-70b-versatile": 128000}


def extract_text_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and "text" in item:
                parts.append(str(item["text"]))
        return "\n".join(parts)
    return str(content)


def calculate_context_usage(
    context: str, model: str = "llama-3.3-70b-versatile"
) -> Dict[str, Any]:
    tokens = len(context) // 4
    max_tokens = MODEL_TOKEN_LIMITS.get(model, 128000)
    percent = round((tokens / max_tokens) * 100, 1)
    return {"tokens": tokens, "max": max_tokens, "percent": percent}


def monitor_context_window(
    context: str, model: str = "llama-3.3-70b-versatile"
) -> Dict[str, Any]:
    res = calculate_context_usage(context, model)
    percent = float(res["percent"])
    res["status"] = (
        "ok" if percent < 50 else ("warning" if percent < 80 else "critical")
    )
    return res
