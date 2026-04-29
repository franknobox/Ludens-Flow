from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from ludens_flow.core.schemas.json_objects import extract_structured_json_object


COPYWRITING_RESPONSE_SCHEMA_TEXT = (
    "Return only one valid JSON object for the Design copywriting task:\n"
    "{\n"
    '  "candidates": [\n'
    '    {"id": "c1", "text": "candidate copy", "notes": ["why it fits"], "tags": ["dialogue"]}\n'
    "  ]\n"
    "}\n"
    "Do not include Markdown fences, comments, or extra prose outside the JSON object."
)


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


@dataclass
class DesignCopywritingContext:
    project_id: str
    artifacts: list[DesignCopywritingContextItem] = field(default_factory=list)
    characters: list[DesignCopywritingContextItem] = field(default_factory=list)
    terms: list[DesignCopywritingContextItem] = field(default_factory=list)
    constraints: list[DesignCopywritingContextItem] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "artifacts": [item.to_dict() for item in self.artifacts],
            "characters": [item.to_dict() for item in self.characters],
            "terms": [item.to_dict() for item in self.terms],
            "constraints": [item.to_dict() for item in self.constraints],
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
class DesignCopywritingResponse:
    request: DesignCopywritingRequest
    candidates: list[DesignCopywritingCandidate] = field(default_factory=list)
    context: DesignCopywritingContext | None = None
    prompt_preview: str = ""
    status: str = "mock"

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "request": self.request.to_dict(),
            "candidates": [candidate.to_dict() for candidate in self.candidates],
            "context": self.context.to_dict() if self.context else None,
            "prompt_preview": self.prompt_preview,
        }


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

    return DesignCopywritingResponse(
        request=request.normalized(),
        candidates=candidates,
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
