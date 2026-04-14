from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from ludens_flow.schemas.json_objects import extract_structured_json_object

REVIEW_GATE_SCHEMA_TEXT = (
    "在回复末尾必须输出一段 ReviewGate JSON，使用以下标记包裹：\n"
    "<<REVIEW_GATE_JSON>>\n"
    "{\n"
    '  "status": "PASS" 或 "REQUEST_CHANGES" 或 "BLOCK",\n'
    '  "targets": ["GDD", "PM", "ENG"],\n'
    '  "scores": {"design": 8, "engineering": 7},\n'
    '  "issues": [\n'
    '    {"target": "ENG", "severity": "MAJOR", "summary": "问题摘要", "fix_hint": "修复建议"}\n'
    "  ]\n"
    "}\n"
    "<<END_REVIEW_GATE_JSON>>"
)

VALID_REVIEW_STATUSES = {"PASS", "REQUEST_CHANGES", "BLOCK"}
VALID_REVIEW_TARGETS = {"GDD", "PM", "ENG"}


@dataclass
class ReviewIssue:
    target: str
    severity: str
    summary: str
    fix_hint: str = ""


@dataclass
class ReviewGatePayload:
    status: str = "REQUEST_CHANGES"
    targets: list[str] = field(default_factory=list)
    scores: dict[str, float] = field(default_factory=dict)
    issues: list[ReviewIssue] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "targets": self.targets,
            "scores": self.scores,
            "issues": [
                {
                    "target": issue.target,
                    "severity": issue.severity,
                    "summary": issue.summary,
                    "fix_hint": issue.fix_hint,
                }
                for issue in self.issues
            ],
        }


def _normalize_targets(raw_targets: Any) -> list[str]:
    if raw_targets is None:
        return []
    if not isinstance(raw_targets, list):
        raw_targets = [raw_targets]

    targets: list[str] = []
    for item in raw_targets:
        candidate = str(item).strip().upper()
        if candidate in VALID_REVIEW_TARGETS and candidate not in targets:
            targets.append(candidate)
    return targets


def _normalize_scores(raw_scores: Any) -> dict[str, float]:
    if not isinstance(raw_scores, dict):
        return {}

    scores: dict[str, float] = {}
    for key in ("design", "engineering"):
        value = raw_scores.get(key)
        if isinstance(value, (int, float)):
            scores[key] = max(0.0, min(10.0, float(value)))
    return scores


def _normalize_issues(raw_issues: Any) -> list[ReviewIssue]:
    if raw_issues is None:
        return []
    if not isinstance(raw_issues, list):
        raw_issues = [raw_issues]

    issues: list[ReviewIssue] = []
    for item in raw_issues:
        if not isinstance(item, dict):
            continue
        target = str(item.get("target", "")).strip().upper()
        severity = str(item.get("severity", "")).strip().upper()
        summary = str(item.get("summary", "")).strip()
        fix_hint = str(item.get("fix_hint", "")).strip()

        if target not in VALID_REVIEW_TARGETS or not severity or not summary:
            continue

        issues.append(
            ReviewIssue(
                target=target,
                severity=severity,
                summary=summary,
                fix_hint=fix_hint,
            )
        )
    return issues


def normalize_review_gate_payload(data: dict[str, Any]) -> ReviewGatePayload:
    status = str(data.get("status", "REQUEST_CHANGES")).strip().upper()
    if status not in VALID_REVIEW_STATUSES:
        status = "REQUEST_CHANGES"

    return ReviewGatePayload(
        status=status,
        targets=_normalize_targets(data.get("targets", [])),
        scores=_normalize_scores(data.get("scores", {})),
        issues=_normalize_issues(data.get("issues", [])),
    )


def parse_review_gate_payload(
    report_text: str,
) -> tuple[Optional[ReviewGatePayload], str]:
    parsed, remaining = extract_structured_json_object(
        report_text,
        tag_name="REVIEW_GATE_JSON",
    )
    if not isinstance(parsed, dict):
        return None, report_text
    return normalize_review_gate_payload(parsed), remaining
