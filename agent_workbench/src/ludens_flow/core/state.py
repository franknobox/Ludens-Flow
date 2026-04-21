"""
文件功能：状态体系设计说明文件，用于展示高层状态架构思路。
核心内容：总结状态数据源、生命周期、迁移策略与一致性模型。
核心内容：提供可读摘要，帮助维护者快速建立状态心智模型。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StateDesign:
    """Top-level state design summary for maintainers."""

    source_of_truth: str
    lifecycle: str
    migration_strategy: str
    consistency_model: str
    auditability: str


STATE_DESIGN = StateDesign(
    source_of_truth=(
        "Project-scoped state files under workspace/projects/<project_id>/state.json, "
        "with artifact metadata and phase-level workflow context."
    ),
    lifecycle=(
        "init workspace -> load/validate/migrate state -> graph/router transitions -> "
        "atomic save with revision checks -> optional reset/export/import."
    ),
    migration_strategy=(
        "Schema versioned payloads with deterministic migration functions and "
        "write-back on successful load."
    ),
    consistency_model=(
        "Optimistic concurrency via revision numbers, stale-write rejection, "
        "and atomic file replace to avoid partial writes."
    ),
    auditability=(
        "Critical lifecycle operations emit audit logs (reset/migrate/export/import) "
        "for replayability and incident tracing."
    ),
)


def describe_state_design() -> str:
    """Return a concise human-readable architecture summary."""

    return (
        "State Design\n"
        f"- Source of truth: {STATE_DESIGN.source_of_truth}\n"
        f"- Lifecycle: {STATE_DESIGN.lifecycle}\n"
        f"- Migration: {STATE_DESIGN.migration_strategy}\n"
        f"- Consistency: {STATE_DESIGN.consistency_model}\n"
        f"- Auditability: {STATE_DESIGN.auditability}"
    )


__all__ = ["StateDesign", "STATE_DESIGN", "describe_state_design"]
