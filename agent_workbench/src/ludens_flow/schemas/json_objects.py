from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional

logger = logging.getLogger(__name__)


def extract_first_json_object(
    text: str, start: int = 0, end: Optional[int] = None
) -> tuple[Optional[str], Optional[tuple[int, int]]]:
    if end is None or end > len(text):
        end = len(text)

    object_start = -1
    depth = 0
    in_string = False
    escape = False

    for idx in range(start, end):
        ch = text[idx]

        if object_start == -1:
            if ch == "{":
                object_start = idx
                depth = 1
                in_string = False
                escape = False
            continue

        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue

        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[object_start : idx + 1], (object_start, idx + 1)

    return None, None


def parse_json_object_candidate(
    candidate: str, context: str
) -> Optional[dict[str, Any]]:
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError as exc:
        logger.debug("Failed to parse JSON object from %s: %s", context, exc)
        return None
    except Exception as exc:
        logger.debug(
            "Unexpected error while parsing JSON object from %s: %s",
            context,
            exc,
        )
        return None

    if not isinstance(parsed, dict):
        logger.debug("JSON payload from %s is not an object.", context)
        return None

    return parsed


def extract_structured_json_object(
    assistant_text: str,
    *,
    tag_name: Optional[str] = None,
) -> tuple[Optional[dict[str, Any]], str]:
    if not assistant_text or not assistant_text.strip():
        return None, ""

    text = assistant_text.strip()

    fence_match = re.search(r"```json\b", text, re.IGNORECASE)
    if fence_match:
        block_start = fence_match.end()
        block_end = text.find("```", block_start)
        if block_end != -1:
            candidate, _ = extract_first_json_object(
                text, start=block_start, end=block_end
            )
            if candidate:
                parsed = parse_json_object_candidate(candidate, "json_code_fence")
                if parsed is not None:
                    remaining = (
                        text[: fence_match.start()] + text[block_end + 3 :]
                    ).strip()
                    return parsed, remaining
        else:
            logger.debug("Found opening ```json fence without a closing fence.")

    if tag_name:
        start_tag = f"<<{tag_name}>>"
        end_tag = f"<<END_{tag_name}>>"
        start_idx = text.find(start_tag)
        if start_idx != -1:
            content_start = start_idx + len(start_tag)
            end_idx = text.find(end_tag, content_start)
            if end_idx != -1:
                candidate, _ = extract_first_json_object(
                    text, start=content_start, end=end_idx
                )
                if candidate:
                    parsed = parse_json_object_candidate(
                        candidate, f"tag_block:{tag_name}"
                    )
                    if parsed is not None:
                        remaining = (
                            text[:start_idx] + text[end_idx + len(end_tag) :]
                        ).strip()
                        return parsed, remaining
    else:
        generic_tag_match = re.search(r"<<(?!END_)([^>]+)>>", text)
        if generic_tag_match:
            generic_tag_name = generic_tag_match.group(1)
            end_tag = f"<<END_{generic_tag_name}>>"
            end_idx = text.find(end_tag, generic_tag_match.end())
            if end_idx != -1:
                candidate, _ = extract_first_json_object(
                    text, start=generic_tag_match.end(), end=end_idx
                )
                if candidate:
                    parsed = parse_json_object_candidate(
                        candidate, f"tag_block:{generic_tag_name}"
                    )
                    if parsed is not None:
                        remaining = (
                            text[: generic_tag_match.start()]
                            + text[end_idx + len(end_tag) :]
                        ).strip()
                        return parsed, remaining

    start = 0
    while start < len(text):
        candidate, span = extract_first_json_object(text, start=start)
        if not candidate or not span:
            break
        parsed = parse_json_object_candidate(candidate, "free_text")
        if parsed is not None:
            obj_start, obj_end = span
            remaining = (text[:obj_start] + text[obj_end:]).strip()
            return parsed, remaining
        start = span[0] + 1

    return None, text
