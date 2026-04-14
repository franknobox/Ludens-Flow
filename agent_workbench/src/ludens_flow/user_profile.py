from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from ludens_flow.paths import get_workspace_dir, resolve_project_id

logger = logging.getLogger(__name__)


def _find_workspace_dir(
    start_path: Optional[Path] = None, project_id: Optional[str] = None
) -> Path:
    """Return the active workspace directory for the current project."""
    _ = start_path
    return get_workspace_dir(resolve_project_id(project_id))


def _profile_path(project_id: Optional[str] = None) -> Path:
    """Return the USER_PROFILE.md path and ensure the workspace exists."""
    ws = _find_workspace_dir(project_id=project_id)
    ws.mkdir(parents=True, exist_ok=True)
    return ws / "USER_PROFILE.md"


_TEMPLATE = """
# USER_PROFILE

> This file is maintained by the system and updated from agent observations.
> Keep the structure stable so both humans and agents can read it reliably.

## Core Identity
- nickname:
- role_or_background:
- current_working_mode:

## Preferences
- gameplay_preferences:
- aesthetic_preferences:
- communication_preferences:

## Project Context
- current_project_goal:
- target_scope:
- timeline_expectation:
- toolchain_preferences:

## Constraints & Risks
- skill_confidence:
- major_limitations:
- resource_constraints:

## Agent Working Notes

### Design
- 

### PM
- 

### Engineering
- 
""".lstrip()


def _extract_labeled_value(text: str, label: str) -> str:
    pattern = rf"^\s*-\s*\*\*{re.escape(label)}\*\*:\s*(.+)$"
    match = re.search(pattern, text, re.MULTILINE)
    if not match:
        return ""
    return match.group(1).strip()


def migrate_profile_text_to_current_template(profile_text: str) -> str:
    """Migrate the legacy USER_PROFILE layout into the current template."""
    if not profile_text or not profile_text.strip():
        return _TEMPLATE

    if profile_text.lstrip().startswith("# USER_PROFILE"):
        return profile_text

    nickname = _extract_labeled_value(profile_text, "代号/昵称")
    current_goal = _extract_labeled_value(profile_text, "核心诉求")
    current_mode = _extract_labeled_value(profile_text, "当前状态")
    engine_skill = _extract_labeled_value(profile_text, "引擎熟练度")
    coding_skill = _extract_labeled_value(profile_text, "编程能力")
    art_skill = _extract_labeled_value(profile_text, "美术能力")
    limitations = _extract_labeled_value(profile_text, "短板警报")
    gameplay_preferences = _extract_labeled_value(profile_text, "核心游戏品类")
    aesthetic_preferences = _extract_labeled_value(profile_text, "视觉风格")
    communication_preferences = _extract_labeled_value(profile_text, "沟通偏好")
    timeline_expectation = _extract_labeled_value(profile_text, "工期预期")
    resource_constraints = _extract_labeled_value(profile_text, "资源限制")
    toolchain_preferences = _extract_labeled_value(profile_text, "工具链偏好")

    design_notes = _extract_agent_notes(profile_text, "Design")
    pm_notes = _extract_agent_notes(profile_text, "PM")
    eng_notes = _extract_agent_notes(profile_text, "Eng")

    skill_details = []
    if engine_skill:
        skill_details.append(f"- engine_skill: {engine_skill}")
    if coding_skill:
        skill_details.append(f"- coding_skill: {coding_skill}")
    if art_skill:
        skill_details.append(f"- art_skill: {art_skill}")

    sections = [
        "# USER_PROFILE",
        "",
        "> Migrated from the legacy profile layout.",
        "> Original information has been preserved and reorganized into the current structure.",
        "",
        "## Core Identity",
        f"- nickname: {nickname}",
        "- role_or_background:",
        f"- current_working_mode: {current_mode}",
        "",
        "## Preferences",
        f"- gameplay_preferences: {gameplay_preferences}",
        f"- aesthetic_preferences: {aesthetic_preferences}",
        f"- communication_preferences: {communication_preferences}",
        "",
        "## Project Context",
        f"- current_project_goal: {current_goal}",
        "- target_scope:",
        f"- timeline_expectation: {timeline_expectation}",
        f"- toolchain_preferences: {toolchain_preferences}",
        "",
        "## Constraints & Risks",
        "- skill_confidence:",
        f"- major_limitations: {limitations}",
        f"- resource_constraints: {resource_constraints}",
        "",
    ]

    if skill_details:
        sections.extend(
            [
                "## Migrated Legacy Details",
                *skill_details,
                "",
            ]
        )

    sections.extend(
        [
            "## Agent Working Notes",
            "",
            "### Design",
            *(design_notes or ["- "]),
            "",
            "### PM",
            *(pm_notes or ["- "]),
            "",
            "### Engineering",
            *(eng_notes or ["- "]),
            "",
        ]
    )

    return "\n".join(sections).strip() + "\n"


def _extract_agent_notes(text: str, agent_name: str) -> list[str]:
    pattern = rf"^### .*?\[{re.escape(agent_name)} .*?\]\s*$"
    match = re.search(pattern, text, re.MULTILINE)
    if not match:
        return []

    section_start = match.end()
    next_match = re.search(r"^### ", text[section_start:], re.MULTILINE)
    if next_match:
        block = text[section_start : section_start + next_match.start()]
    else:
        block = text[section_start:]

    notes: list[str] = []
    for raw_line in block.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            continue
        if line.lstrip().startswith("-"):
            notes.append(line.strip())

    return notes


def load_profile(max_chars: int = 2000, project_id: Optional[str] = None) -> str:
    """Read USER_PROFILE.md, creating the template when the file is missing."""
    path = _profile_path(project_id)
    if not path.exists():
        try:
            path.write_text(_TEMPLATE, encoding="utf-8")
            logger.info("Created new USER_PROFILE at %s", path)
        except Exception as exc:
            logger.error("Failed to create profile template: %s", exc)
            return _TEMPLATE[:max_chars]

    try:
        text = path.read_text(encoding="utf-8")
        if not text.strip():
            path.write_text(_TEMPLATE, encoding="utf-8")
            return _TEMPLATE[:max_chars]
        return text[:max_chars]
    except Exception as exc:
        logger.error("Failed to read profile: %s", exc)
        return _TEMPLATE[:max_chars]


def format_profile_for_prompt(profile_text: str) -> str:
    """Turn USER_PROFILE markdown into a compact prompt-friendly context block."""
    if not profile_text or not profile_text.strip():
        return ""

    lines = [line.rstrip() for line in profile_text.splitlines()]
    normalized: list[str] = []

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue

        line = re.sub(r"^>+\s*", "", line)
        line = re.sub(r"^\[\![^\]]+\]\s*", "", line)

        if line.startswith("#"):
            title = line.lstrip("#").strip()
            if title:
                normalized.append(f"[Section] {title}")
            continue

        normalized.append(line)

    profile_body = "\n".join(normalized).strip()
    if not profile_body:
        return ""

    return (
        "[PROFILE USAGE RULES]\n"
        "- Only use this profile when the answer involves the user's identity, preferences, habits, communication style, or long-term project goals.\n"
        "- If the current user message conflicts with the stored profile, trust the current user message first.\n"
        "- Do not force-profile every answer; use it only when it meaningfully improves the guidance.\n"
        "- When you do use profile information, keep the advice consistent with the user's stated constraints and goals.\n\n"
        "[USER PROFILE CONTEXT]\n"
        f"{profile_body}"
    )


def migrate_profile_file(project_id: Optional[str] = None) -> bool:
    """Rewrite an existing legacy USER_PROFILE.md into the current template."""
    path = _profile_path(project_id)
    if not path.exists():
        return False

    try:
        current_text = path.read_text(encoding="utf-8")
    except Exception as exc:
        logger.error("Failed to read profile for migration: %s", exc)
        return False

    migrated_text = migrate_profile_text_to_current_template(current_text)
    if migrated_text == current_text:
        return False

    try:
        tmp = path.with_suffix(".tmp")
        tmp.write_text(migrated_text, encoding="utf-8")
        tmp.replace(path)
        logger.info("Migrated USER_PROFILE to the current template at %s", path)
        return True
    except Exception as exc:
        logger.error("Failed to migrate USER_PROFILE: %s", exc)
        return False


def update_profile(
    entries: List[str], author: str = "agent", project_id: Optional[str] = None
) -> bool:
    """Append new entries to USER_PROFILE.md while skipping blanks and duplicates."""
    if not entries:
        return False

    path = _profile_path(project_id)
    try:
        if not path.exists():
            path.write_text(_TEMPLATE, encoding="utf-8")
        text = path.read_text(encoding="utf-8")
    except Exception as exc:
        logger.error("Failed to prepare profile for update: %s", exc)
        return False

    changed = False
    appended_lines: List[str] = []
    for entry in entries:
        value = entry.strip()
        if not value:
            continue
        if value in text:
            continue
        timestamp = (
            datetime.now(timezone.utc)
            .isoformat(timespec="seconds")
            .replace("+00:00", "Z")
        )
        appended_lines.append(f"- [{timestamp}] ({author}) {value}")
        changed = True

    if not changed:
        return False

    new_text = text.rstrip() + "\n\n" + "\n".join(appended_lines) + "\n"
    try:
        tmp = path.with_suffix(".tmp")
        tmp.write_text(new_text, encoding="utf-8")
        tmp.replace(path)
        logger.info("USER_PROFILE updated with %s entries", len(appended_lines))
        return True
    except Exception as exc:
        logger.error("Failed to write USER_PROFILE: %s", exc)
        return False
