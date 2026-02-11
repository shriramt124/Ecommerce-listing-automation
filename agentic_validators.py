"""Small schema validators for LLM JSON outputs.

Kept intentionally lightweight (no pydantic) to minimize dependencies.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


def _is_str_list(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(x, str) for x in value)


def validate_category_info(obj: Any) -> Tuple[bool, List[str]]:
    errors: List[str] = []
    if not isinstance(obj, dict):
        return False, ["not an object"]

    for key in ["category", "subcategory"]:
        if not isinstance(obj.get(key), str) or not obj.get(key).strip():
            errors.append(f"missing/invalid '{key}'")

    if obj.get("key_attributes") is not None and not _is_str_list(obj.get("key_attributes")):
        errors.append("'key_attributes' must be a list of strings")

    if obj.get("search_priorities") is not None and not _is_str_list(obj.get("search_priorities")):
        errors.append("'search_priorities' must be a list of strings")

    if obj.get("color_important") is not None and not isinstance(obj.get("color_important"), bool):
        errors.append("'color_important' must be boolean")

    return len(errors) == 0, errors


def validate_concept_eval(obj: Any) -> Tuple[bool, List[str]]:
    errors: List[str] = []
    if not isinstance(obj, dict):
        return False, ["not an object"]

    if not isinstance(obj.get("keep"), bool):
        errors.append("missing/invalid 'keep'")

    if obj.get("value_score") is not None and not isinstance(obj.get("value_score"), (int, float)):
        errors.append("'value_score' must be a number")

    if obj.get("position") is not None and not isinstance(obj.get("position"), str):
        errors.append("'position' must be a string")

    if obj.get("reason") is not None and not isinstance(obj.get("reason"), str):
        errors.append("'reason' must be a string")

    return len(errors) == 0, errors


def validate_query_suggestions(obj: Any) -> Tuple[bool, List[str]]:
    if not isinstance(obj, dict):
        return False, ["not an object"]
    queries = obj.get("queries")
    if not _is_str_list(queries):
        return False, ["'queries' must be a list of strings"]
    return True, []


def validate_keyword_selection(obj: Any) -> Tuple[bool, List[str]]:
    errors: List[str] = []
    if not isinstance(obj, dict):
        return False, ["not an object"]

    sel = obj.get("selected_keywords")
    if not isinstance(sel, list):
        errors.append("'selected_keywords' must be a list")
    else:
        for i, item in enumerate(sel[:50]):
            if not isinstance(item, dict):
                errors.append(f"selected_keywords[{i}] is not an object")
                continue
            if not isinstance(item.get("keyword"), str) or not item.get("keyword").strip():
                errors.append(f"selected_keywords[{i}].keyword missing/invalid")
            # Zone field is optional but if present should be string
            if item.get("zone") is not None and not isinstance(item.get("zone"), str):
                errors.append(f"selected_keywords[{i}].zone must be string")
            if item.get("reason") is not None and not isinstance(item.get("reason"), str):
                errors.append(f"selected_keywords[{i}].reason must be string")

    if obj.get("rejected_count") is not None and not isinstance(obj.get("rejected_count"), (int, float)):
        errors.append("'rejected_count' must be a number")

    if obj.get("rejection_reasons") is not None and not _is_str_list(obj.get("rejection_reasons")):
        errors.append("'rejection_reasons' must be a list of strings")

    return len(errors) == 0, errors


def validate_title_draft(obj: Any) -> Tuple[bool, List[str]]:
    errors: List[str] = []
    if not isinstance(obj, dict):
        return False, ["not an object"]

    if not isinstance(obj.get("full_title"), str) or not obj.get("full_title").strip():
        errors.append("missing/invalid 'full_title'")
    elif len(obj.get("full_title")) > 200:
        errors.append(f"full_title is too long ({len(obj.get('full_title'))} chars). STRICT LIMIT: 200 chars. Shorten it.")

    # zones optional but recommended
    for z in ["zone_a", "zone_b", "zone_c"]:
        if obj.get(z) is not None and not isinstance(obj.get(z), str):
            errors.append(f"'{z}' must be a string")

    if obj.get("char_count") is not None and not isinstance(obj.get("char_count"), (int, float)):
        errors.append("'char_count' must be a number")

    if obj.get("reasoning") is not None and not isinstance(obj.get("reasoning"), dict):
        errors.append("'reasoning' must be an object")

    return len(errors) == 0, errors
