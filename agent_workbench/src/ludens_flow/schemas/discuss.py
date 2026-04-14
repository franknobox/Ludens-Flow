from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from ludens_flow.schemas.json_objects import extract_structured_json_object

DISCUSS_RESPONSE_SCHEMA_TEXT = (
    "请严格只输出一个合法的 JSON 对象，不要包含额外解释、注释或代码围栏。"
    "\nJSON 格式如下：\n"
    "{\n"
    '  "reply": "显示给用户的自然语言回答",\n'
    '  "state_updates": {},\n'
    '  "profile_updates": ["[PROFILE_UPDATE] key: value"],\n'
    '  "events": []\n'
    "}\n"
    "重要：如果某个字段没有内容，请使用 null、{} 或 []，不要输出多余文本。"
)


@dataclass
class DiscussPayload:
    reply: str = ""
    state_updates: dict[str, Any] = field(default_factory=dict)
    profile_updates: list[str] = field(default_factory=list)
    events: list[str] = field(default_factory=list)


def normalize_discuss_payload(
    data: dict[str, Any], fallback_reply: str = ""
) -> DiscussPayload:
    reply = data.get("reply", fallback_reply or "")
    if reply is None:
        reply = fallback_reply or ""
    if not isinstance(reply, str):
        reply = str(reply)

    state_updates = data.get("state_updates", {})
    if not isinstance(state_updates, dict):
        state_updates = {}

    raw_profile_updates = data.get("profile_updates", [])
    if raw_profile_updates is None:
        raw_profile_updates = []
    if not isinstance(raw_profile_updates, list):
        raw_profile_updates = [raw_profile_updates]
    profile_updates = [
        str(item)
        for item in raw_profile_updates
        if item is not None and str(item).strip()
    ]

    raw_events = data.get("events", [])
    if raw_events is None:
        raw_events = []
    if not isinstance(raw_events, list):
        raw_events = [raw_events]
    events = [
        str(item)
        for item in raw_events
        if item is not None and str(item).strip()
    ]

    return DiscussPayload(
        reply=reply.strip(),
        state_updates=state_updates,
        profile_updates=profile_updates,
        events=events,
    )


def parse_discuss_payload(assistant_text: str) -> tuple[Optional[DiscussPayload], str]:
    parsed, remaining = extract_structured_json_object(assistant_text)
    if not isinstance(parsed, dict):
        return None, remaining
    return normalize_discuss_payload(parsed, fallback_reply=remaining), remaining
