"""Skill authoring tools exposed through the controlled tool registry."""

from __future__ import annotations

import json
from typing import Any, Optional

from ludens_flow.capabilities.skills.registry import create_skill_draft


def skill_create_draft(
    manifest: dict[str, Any],
    prompt: str,
    *,
    project_id: Optional[str] = None,
    source_agent: str = "",
    reason: str = "",
) -> str:
    skill = create_skill_draft(
        manifest,
        prompt=prompt,
        project_id=project_id,
        source_agent=source_agent,
        reason=reason,
    )
    return json.dumps({"self_skill": skill}, ensure_ascii=False, indent=2)


SKILL_CREATE_DRAFT_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "skill_create_draft",
        "description": (
            "Create a self-learned Skill from a repeated useful workflow. "
            "The Skill is installed globally, but each project still decides whether to enable it."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "manifest": {
                    "type": "object",
                    "description": "Skill manifest with name, description, agents, and tags.",
                },
                "prompt": {
                    "type": "string",
                    "description": "Reusable Skill instructions in Markdown.",
                },
                "source_agent": {
                    "type": "string",
                    "description": "Agent that proposed this Skill.",
                },
                "reason": {
                    "type": "string",
                    "description": "Why this workflow should become a Skill.",
                },
            },
            "required": ["manifest", "prompt"],
        },
    },
}
