from __future__ import annotations

from typing import Iterable

from llm.modelrouter import resolve_model_config
from llm.provider import generate
from ludens_flow.capabilities.artifacts.artifacts import read_artifact
from ludens_flow.core.paths import resolve_project_id
from ludens_flow.core.schemas import (
    COPYWRITING_RESPONSE_SCHEMA_TEXT,
    DesignCopywritingContext,
    DesignCopywritingContextItem,
    DesignCopywritingRequest,
    DesignCopywritingResponse,
    normalize_design_copywriting_response,
    parse_design_copywriting_response,
)

_ARTIFACT_REFERENCES = {
    "gdd": ("GDD", "GDD.md"),
    "project_plan": ("PROJECT_PLAN", "PROJECT_PLAN.md"),
    "implementation_plan": ("IMPLEMENTATION_PLAN", "IMPLEMENTATION_PLAN.md"),
    "review_report": ("REVIEW_REPORT", "REVIEW_REPORT.md"),
    "devlog": ("DEVLOG", "dev_notes/DEVLOG.md"),
    "notes": ("NOTES", "dev_notes/NOTES.md"),
}

_DEFAULT_REFERENCE_IDS = ["gdd", "project_plan"]
_MAX_CONTEXT_CHARS_PER_ITEM = 5000


def load_design_copywriting_context(
    project_id: str | None,
    reference_ids: Iterable[str] | None = None,
) -> DesignCopywritingContext:
    resolved_project_id = resolve_project_id(project_id)
    requested = [str(item).strip() for item in (reference_ids or []) if str(item).strip()]
    if not requested:
        requested = list(_DEFAULT_REFERENCE_IDS)

    context = DesignCopywritingContext(project_id=resolved_project_id)
    for reference_id in requested:
        artifact_info = _ARTIFACT_REFERENCES.get(reference_id)
        if not artifact_info:
            continue

        artifact_name, display_name = artifact_info
        content = _truncate_context(read_artifact(artifact_name, project_id=resolved_project_id))
        if not content.strip():
            continue

        item = DesignCopywritingContextItem(
            id=reference_id,
            name=display_name,
            source="artifact",
            content=content,
        )
        context.artifacts.append(item)

    return context


def build_design_copywriting_prompt(
    request: DesignCopywritingRequest,
    context: DesignCopywritingContext,
) -> str:
    normalized = request.normalized()
    context_blocks = []
    for item in context.artifacts:
        context_blocks.append(
            f"### {item.name}\n"
            f"{item.content.strip()}"
        )

    context_text = "\n\n".join(context_blocks).strip() or "No project artifacts were selected."
    must_include = ", ".join(normalized.must_include) or "None"
    must_avoid = ", ".join(normalized.must_avoid) or "None"

    return (
        "You are Dam / Design, using your game design understanding of the current project "
        "to produce usable in-game copywriting candidates.\n\n"
        "Task boundary:\n"
        "- This is a Design Agent sub-capability, not a separate agent and not a PM planning task.\n"
        "- Generate project-aware copywriting only; do not revise the GDD or project plan here.\n"
        "- Respect the project artifacts as source-of-truth context.\n\n"
        "Request:\n"
        f"- Copy type: {normalized.copy_type}\n"
        f"- Purpose: {normalized.purpose or 'Not specified'}\n"
        f"- Brief: {normalized.brief or 'Not specified'}\n"
        f"- Quantity: {normalized.quantity}\n"
        f"- Writing style: {normalized.style}\n"
        f"- Length: {normalized.length}\n"
        f"- Must include: {must_include}\n"
        f"- Must avoid: {must_avoid}\n"
        f"- Language: {normalized.language}\n\n"
        "Project context:\n"
        f"{context_text}\n\n"
        f"{COPYWRITING_RESPONSE_SCHEMA_TEXT}"
    )


def generate_design_copywriting(
    request: DesignCopywritingRequest,
    *,
    project_id: str | None = None,
) -> DesignCopywritingResponse:
    normalized = request.normalized()
    resolved_project_id = resolve_project_id(project_id)
    context = load_design_copywriting_context(resolved_project_id, normalized.reference_ids)
    prompt = build_design_copywriting_prompt(normalized, context)

    cfg = resolve_model_config(
        project_id=resolved_project_id,
        agent_key="design",
        capability="copywriting",
        default_route={"temperature": 0.7},
    )
    raw = generate(
        system=(
            "You are Dam / Design, the design agent of Ludens-Flow. "
            "Generate concise, usable game copywriting and return only the requested JSON object."
        ),
        user=prompt,
        cfg=cfg,
    )

    response, _ = parse_design_copywriting_response(
        str(raw or ""),
        request=normalized,
        context=context,
        prompt_preview=prompt,
    )
    if response and response.candidates:
        return response

    # If the model ignored the JSON contract, keep the feature usable by wrapping
    # the raw text as one candidate instead of discarding the generation.
    return normalize_design_copywriting_response(
        {"candidates": [{"id": "c1", "text": str(raw or "").strip()}]},
        request=normalized,
        context=context,
        prompt_preview=prompt,
        status="generated",
    )


def _truncate_context(content: str) -> str:
    text = str(content or "").strip()
    if len(text) <= _MAX_CONTEXT_CHARS_PER_ITEM:
        return text
    return text[:_MAX_CONTEXT_CHARS_PER_ITEM].rstrip() + "\n\n[Context truncated]"
