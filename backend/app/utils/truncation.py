from typing import Any


def truncate_string(text: str, max_chars: int = 300) -> str:
    """Trim a string to max_chars with ellipsis."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars - 3] + "..."


def truncate_list(data: list, max_items: int = 5) -> list:
    """Trim any list to max_items."""
    return data[:max_items]


def truncate_output(data: Any, max_items: int = 5, max_chars: int = 300) -> Any:
    """
    Central truncation utility — call before anything goes to LLM.
    Handles dicts, lists, and strings recursively.
    """
    if isinstance(data, dict):
        return {k: truncate_output(v, max_items, max_chars) for k, v in data.items()}
    if isinstance(data, list):
        return [truncate_output(item, max_items, max_chars) for item in data[:max_items]]
    if isinstance(data, str):
        return truncate_string(data, max_chars)
    return data