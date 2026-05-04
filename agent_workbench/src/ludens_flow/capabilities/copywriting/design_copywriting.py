from __future__ import annotations

from typing import Callable, Iterable

from llm.modelrouter import resolve_model_config
from llm.provider import generate
from ludens_flow.capabilities.artifacts.artifacts import read_artifact
from ludens_flow.capabilities.ingest.attachment_ingest import build_attachment_user_input
from ludens_flow.core.paths import resolve_project_id
from ludens_flow.core.schemas import (
    DIALOGUE_CSV_COLUMNS,
    DesignCopywritingContext,
    DesignCopywritingContextItem,
    DesignCopywritingRequest,
    DesignCopywritingResponse,
    copywriting_response_schema_for,
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

_DEFAULT_REFERENCE_IDS = ["gdd"]
_MAX_CONTEXT_CHARS_PER_ITEM = 5000


def load_design_copywriting_context(
    project_id: str | None,
    reference_ids: Iterable[str] | None = None,
    external_references: list[dict] | None = None,
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

    for index, external_item in enumerate(external_references or [], start=1):
        item = _external_reference_context_item(index, external_item)
        if item:
            context.external_files.append(item)

    return context


def build_design_copywriting_prompt(
    request: DesignCopywritingRequest,
    context: DesignCopywritingContext,
) -> str:
    normalized = request.normalized()
    context_blocks = []
    for item in [*context.artifacts, *context.external_files]:
        context_blocks.append(
            f"### {item.name}\n"
            f"{item.content.strip()}"
        )

    context_text = "\n\n".join(context_blocks).strip() or "No project artifacts were selected."
    must_include = ", ".join(normalized.must_include) or "None"
    must_avoid = ", ".join(normalized.must_avoid) or "None"
    output_instruction = "Output requirement:\n- Return candidate copywriting only.\n"
    if normalized.copy_type == "dialogue":
        output_instruction = (
            "Dialogue CSV output requirement:\n"
            "- Also return table.kind = \"dialogue_csv\".\n"
            f"- table.columns must be exactly: {', '.join(DIALOGUE_CSV_COLUMNS)}.\n"
            "- table.rows must contain one row per dialogue line, suitable for direct CSV export into a game editor.\n"
            "- Use stable ids like dlg_001, dlg_002. Fill unknown fields with empty strings, not null.\n"
            "- npc should contain the speaker name when the brief provides one; otherwise leave it empty.\n"
            "- next_id should link to the next row when these lines form a sequence; otherwise leave it empty.\n"
        )

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
        f"{output_instruction}\n"
        "Project context:\n"
        f"{context_text}\n\n"
        f"{copywriting_response_schema_for(normalized.copy_type)}"
    )


def generate_design_copywriting(
    request: DesignCopywritingRequest,
    *,
    project_id: str | None = None,
    external_references: list[dict] | None = None,
    progress_handler: Callable[[str], None] | None = None,
) -> DesignCopywritingResponse:
    normalized = request.normalized()
    resolved_project_id = resolve_project_id(project_id)
    if progress_handler:
        progress_handler("正在读取已选择的项目工件和外部资料...")
    context = load_design_copywriting_context(
        resolved_project_id,
        normalized.reference_ids,
        external_references,
    )
    if progress_handler:
        progress_handler("正在构建文案输出契约...")
    prompt = build_design_copywriting_prompt(normalized, context)

    cfg = resolve_model_config(
        project_id=resolved_project_id,
        agent_key="design",
        capability="copywriting",
        default_route={"temperature": 0.7, "timeout": 120},
    )
    if progress_handler:
        progress_handler("Dam / Design 正在生成候选文案...")
    raw = generate(
        system=(
            "You are Dam / Design, the design agent of Ludens-Flow. "
            "Generate concise, usable game copywriting and return only the requested JSON object."
        ),
        user=prompt,
        cfg=cfg,
    )

    if progress_handler:
        progress_handler("正在解析结构化结果...")
    response, _ = parse_design_copywriting_response(
        str(raw or ""),
        request=normalized,
        context=context,
        prompt_preview=prompt,
    )
    if response and response.candidates:
        if progress_handler:
            progress_handler("正在整理候选结果与导出表格...")
        return response

    # If the model ignored the JSON contract, keep the feature usable by wrapping
    # the raw text as one candidate instead of discarding the generation.
    if progress_handler:
        progress_handler("正在整理候选结果与导出表格...")
    return normalize_design_copywriting_response(
        {"candidates": [{"id": "c1", "text": str(raw or "").strip()}]},
        request=normalized,
        context=context,
        prompt_preview=prompt,
        status="generated",
    )


def _truncate_context(content: str, *, max_chars: int = _MAX_CONTEXT_CHARS_PER_ITEM) -> str:
    text = str(content or "").strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "\n\n[Context truncated]"


def _external_reference_context_item(
    index: int,
    external_item: dict,
) -> DesignCopywritingContextItem | None:
    name = str(external_item.get("name") or f"external-reference-{index}").strip()
    data_url = str(external_item.get("data_url") or external_item.get("dataUrl") or "")
    if not data_url.startswith("data:"):
        return None

    payload = build_attachment_user_input(
        "",
        attachments=[
            {
                "kind": "file",
                "name": name,
                "data_url": data_url,
            }
        ],
    )

    text_parts: list[str] = []
    if isinstance(payload.user_input, list):
        for part in payload.user_input:
            if isinstance(part, dict) and part.get("type") == "text":
                text = str(part.get("text") or "").strip()
                if text:
                    text_parts.append(text)
    elif payload.user_input:
        text_parts.append(str(payload.user_input).strip())

    content = _truncate_context("\n\n".join(text_parts), max_chars=_MAX_CONTEXT_CHARS_PER_ITEM)
    if not content.strip() or "[Attached File]" not in content:
        return None

    return DesignCopywritingContextItem(
        id=f"external_file_{index}",
        name=name,
        source="external_file",
        content=content,
    )
