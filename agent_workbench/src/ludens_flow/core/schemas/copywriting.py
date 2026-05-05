from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from ludens_flow.core.schemas.json_objects import extract_structured_json_object


COPYWRITING_CANDIDATES_SCHEMA_TEXT = (
    "Return only one valid JSON object for the Design copywriting task:\n"
    "{\n"
    '  "candidates": [\n'
    '    {"id": "c1", "text": "candidate copy", "notes": ["why it fits"], "tags": ["dialogue"]}\n'
    "  ],\n"
    "}\n"
    "Do not include Markdown fences, comments, or extra prose outside the JSON object."
)

COPYWRITING_DIALOGUE_SCHEMA_TEXT = (
    "Return only one valid JSON object for the Design dialogue copywriting task:\n"
    "{\n"
    '  "candidates": [\n'
    '    {"id": "c1", "text": "candidate dialogue", "notes": ["why it fits"], "tags": ["dialogue"]}\n'
    "  ],\n"
    '  "table": {\n'
    '    "kind": "dialogue_csv",\n'
    '    "columns": ["id", "npc", "scene", "trigger", "text", "emotion", "next_id", "condition"],\n'
    '    "rows": [\n'
    '      {"id": "dlg_001", "npc": "Bob", "scene": "shop", "trigger": "first_meet", "text": "candidate dialogue", "emotion": "casual", "next_id": "", "condition": ""}\n'
    "    ]\n"
    "  }\n"
    "}\n"
    "Do not include Markdown fences, comments, or extra prose outside the JSON object."
)


def copywriting_response_schema_for(copy_type: str) -> str:
    if str(copy_type or "").strip().lower() == "dialogue":
        return COPYWRITING_DIALOGUE_SCHEMA_TEXT
    return COPYWRITING_CANDIDATES_SCHEMA_TEXT

DIALOGUE_CSV_COLUMNS = [
    "id",
    "npc",
    "scene",
    "trigger",
    "text",
    "emotion",
    "next_id",
    "condition",
]


@dataclass
class DesignCopywritingRequest:
    copy_type: str
    brief: str = ""
    purpose: str = ""
    quantity: int = 5
    style: str = "简洁直给"
    length: str = "标准"
    must_include: list[str] = field(default_factory=list)
    must_avoid: list[str] = field(default_factory=list)
    reference_ids: list[str] = field(default_factory=list)
    language: str = "zh-CN"

    def normalized(self) -> "DesignCopywritingRequest":
        return DesignCopywritingRequest(
            copy_type=_clean_text(self.copy_type) or "dialogue",
            brief=_clean_text(self.brief),
            purpose=_clean_text(self.purpose),
            quantity=max(1, min(30, _coerce_int(self.quantity, 5))),
            style=_clean_text(self.style) or "简洁直给",
            length=_clean_text(self.length) or "标准",
            must_include=_clean_string_list(self.must_include),
            must_avoid=_clean_string_list(self.must_avoid),
            reference_ids=_clean_string_list(self.reference_ids),
            language=_clean_text(self.language) or "zh-CN",
        )

    def to_dict(self) -> dict[str, Any]:
        normalized = self.normalized()
        return {
            "copy_type": normalized.copy_type,
            "brief": normalized.brief,
            "purpose": normalized.purpose,
            "quantity": normalized.quantity,
            "style": normalized.style,
            "length": normalized.length,
            "must_include": normalized.must_include,
            "must_avoid": normalized.must_avoid,
            "reference_ids": normalized.reference_ids,
            "language": normalized.language,
        }


@dataclass
class DesignCopywritingContextItem:
    id: str
    name: str
    source: str
    content: str

    def to_dict(self) -> dict[str, str]:
        return {
            "id": self.id,
            "name": self.name,
            "source": self.source,
            "content": self.content,
        }

    def to_meta_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "source": self.source,
            "content_chars": len(self.content or ""),
        }


@dataclass
class DesignCopywritingContext:
    project_id: str
    artifacts: list[DesignCopywritingContextItem] = field(default_factory=list)
    external_files: list[DesignCopywritingContextItem] = field(default_factory=list)
    characters: list[DesignCopywritingContextItem] = field(default_factory=list)
    terms: list[DesignCopywritingContextItem] = field(default_factory=list)
    constraints: list[DesignCopywritingContextItem] = field(default_factory=list)

    def to_dict(self, *, include_content: bool = False) -> dict[str, Any]:
        serialize = (
            (lambda item: item.to_dict())
            if include_content
            else (lambda item: item.to_meta_dict())
        )
        return {
            "project_id": self.project_id,
            "artifacts": [serialize(item) for item in self.artifacts],
            "external_files": [serialize(item) for item in self.external_files],
            "characters": [serialize(item) for item in self.characters],
            "terms": [serialize(item) for item in self.terms],
            "constraints": [serialize(item) for item in self.constraints],
        }


@dataclass
class DesignCopywritingCandidate:
    id: str
    text: str
    notes: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "text": self.text,
            "notes": self.notes,
            "tags": self.tags,
        }


@dataclass
class DesignCopywritingTable:
    kind: str
    columns: list[str] = field(default_factory=list)
    rows: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "columns": self.columns,
            "rows": self.rows,
        }


@dataclass
class DesignCopywritingResponse:
    request: DesignCopywritingRequest
    candidates: list[DesignCopywritingCandidate] = field(default_factory=list)
    table: DesignCopywritingTable | None = None
    context: DesignCopywritingContext | None = None
    prompt_preview: str = ""
    status: str = "mock"

    def to_dict(
        self,
        *,
        include_prompt_preview: bool = False,
        include_context_content: bool = False,
    ) -> dict[str, Any]:
        payload = {
            "status": self.status,
            "request": self.request.to_dict(),
            "candidates": [candidate.to_dict() for candidate in self.candidates],
            "table": self.table.to_dict() if self.table else None,
            "context": (
                self.context.to_dict(include_content=include_context_content)
                if self.context
                else None
            ),
        }
        if include_prompt_preview:
            payload["prompt_preview"] = self.prompt_preview
        return payload


def normalize_design_copywriting_request(data: dict[str, Any]) -> DesignCopywritingRequest:
    return DesignCopywritingRequest(
        copy_type=str(data.get("copy_type") or data.get("type") or ""),
        brief=str(data.get("brief") or data.get("requirement") or ""),
        purpose=str(data.get("purpose") or ""),
        quantity=_coerce_int(data.get("quantity"), 5),
        style=str(data.get("style") or ""),
        length=str(data.get("length") or ""),
        must_include=_clean_string_list(data.get("must_include") or []),
        must_avoid=_clean_string_list(data.get("must_avoid") or []),
        reference_ids=_clean_string_list(data.get("reference_ids") or []),
        language=str(data.get("language") or "zh-CN"),
    ).normalized()


def normalize_design_copywriting_response(
    data: dict[str, Any],
    *,
    request: DesignCopywritingRequest,
    context: DesignCopywritingContext | None = None,
    prompt_preview: str = "",
    status: str = "generated",
) -> DesignCopywritingResponse:
    raw_candidates = data.get("candidates", [])
    if raw_candidates is None:
        raw_candidates = []
    if not isinstance(raw_candidates, list):
        raw_candidates = [raw_candidates]

    candidates: list[DesignCopywritingCandidate] = []
    for index, raw_candidate in enumerate(raw_candidates):
        if isinstance(raw_candidate, str):
            candidate_data: dict[str, Any] = {"text": raw_candidate}
        elif isinstance(raw_candidate, dict):
            candidate_data = raw_candidate
        else:
            continue

        text = _clean_text(candidate_data.get("text"))
        if not text:
            continue

        candidate_id = _clean_text(candidate_data.get("id")) or f"c{index + 1}"
        candidates.append(
            DesignCopywritingCandidate(
                id=candidate_id,
                text=text,
                notes=_clean_string_list(candidate_data.get("notes") or []),
                tags=_clean_string_list(candidate_data.get("tags") or []),
            )
        )

    table = _normalize_copywriting_table(data.get("table"))
    if table is None and request.normalized().copy_type == "dialogue":
        table = _table_from_dialogue_candidates(candidates)

    return DesignCopywritingResponse(
        request=request.normalized(),
        candidates=candidates,
        table=table,
        context=context,
        prompt_preview=prompt_preview,
        status=status,
    )


def parse_design_copywriting_response(
    assistant_text: str,
    *,
    request: DesignCopywritingRequest,
    context: DesignCopywritingContext | None = None,
    prompt_preview: str = "",
) -> tuple[Optional[DesignCopywritingResponse], str]:
    parsed, remaining = extract_structured_json_object(assistant_text)
    if not isinstance(parsed, dict):
        return None, remaining
    return (
        normalize_design_copywriting_response(
            parsed,
            request=request,
            context=context,
            prompt_preview=prompt_preview,
            status="generated",
        ),
        remaining,
    )


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _normalize_copywriting_table(value: Any) -> DesignCopywritingTable | None:
    if not isinstance(value, dict):
        return None

    columns = _clean_string_list(value.get("columns") or DIALOGUE_CSV_COLUMNS)
    if not columns:
        columns = list(DIALOGUE_CSV_COLUMNS)

    raw_rows = value.get("rows") or []
    if not isinstance(raw_rows, list):
        raw_rows = [raw_rows]

    rows: list[dict[str, str]] = []
    for raw_row in raw_rows:
        if not isinstance(raw_row, dict):
            continue
        row = {column: _clean_text(raw_row.get(column)) for column in columns}
        if any(row.values()):
            rows.append(row)

    if not rows:
        return None

    return DesignCopywritingTable(
        kind=_clean_text(value.get("kind")) or "dialogue_csv",
        columns=columns,
        rows=rows,
    )


def _table_from_dialogue_candidates(
    candidates: list[DesignCopywritingCandidate],
) -> DesignCopywritingTable | None:
    rows: list[dict[str, str]] = []
    for index, candidate in enumerate(candidates, start=1):
        rows.append(
            {
                "id": f"dlg_{index:03d}",
                "npc": "",
                "scene": "",
                "trigger": "",
                "text": candidate.text,
                "emotion": "",
                "next_id": f"dlg_{index + 1:03d}" if index < len(candidates) else "",
                "condition": "",
            }
        )

    if not rows:
        return None

    return DesignCopywritingTable(
        kind="dialogue_csv",
        columns=list(DIALOGUE_CSV_COLUMNS),
        rows=rows,
    )


def _clean_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        raw_items = value.replace("，", ",").split(",")
    elif isinstance(value, list):
        raw_items = value
    else:
        raw_items = [value]

    items: list[str] = []
    for item in raw_items:
        text = _clean_text(item)
        if text and text not in items:
            items.append(text)
    return items


def _coerce_int(value: Any, fallback: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback
