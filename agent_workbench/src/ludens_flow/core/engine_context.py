"""Project engine context helpers for prompt and artifact generation."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional

from ludens_flow.core.paths import (
    REPO_ROOT,
    get_project_settings,
    list_project_workspaces,
    resolve_project_id,
)

ENGINE_LABELS = {
    "generic": "通用小型游戏 demo",
    "unity": "Unity",
    "godot": "Godot",
    "unreal": "Unreal Engine",
}

ENGINE_WORKSPACE_KINDS = {"unity", "godot"}
ENGINE_MCP_KINDS = {"unity", "godot", "unreal"}
ENGINE_FRAGMENT_DIR = Path("agent_workbench") / "prompts" / "engine"


def resolve_project_engine_context(project_id: Optional[str] = None) -> Dict[str, Any]:
    """Resolve explicit project engine settings with conservative inference fallback."""
    resolved = resolve_project_id(project_id)
    settings = get_project_settings(project_id=resolved)
    explicit_engine = str(settings.get("target_engine") or "").strip().lower()
    profile = str(settings.get("engine_profile") or "").strip()

    if explicit_engine:
        return {
            "project_id": resolved,
            "target_engine": explicit_engine,
            "engine_label": ENGINE_LABELS.get(explicit_engine, explicit_engine),
            "engine_profile": profile,
            "source": "explicit",
        }

    inferred = _infer_engine_from_project_bindings(resolved)
    if inferred:
        return {
            "project_id": resolved,
            "target_engine": inferred,
            "engine_label": ENGINE_LABELS.get(inferred, inferred),
            "engine_profile": profile,
            "source": "inferred",
        }

    return {
        "project_id": resolved,
        "target_engine": "generic",
        "engine_label": ENGINE_LABELS["generic"],
        "engine_profile": profile,
        "source": "fallback",
    }


def format_project_engine_for_prompt(project_id: Optional[str] = None) -> str:
    """Format the project engine decision as a compact prompt context block."""
    context = resolve_project_engine_context(project_id)
    engine = context["target_engine"]
    source = context["source"]
    label = context["engine_label"]

    if source == "explicit":
        source_text = "项目设置显式指定"
    elif source == "inferred":
        source_text = "根据当前项目工作区或 MCP 连接推断"
    else:
        source_text = "未配置主引擎，使用保守回退"

    lines = [
        "项目目标引擎上下文：",
        f"- 当前主引擎：{label}",
        f"- 来源：{source_text}",
    ]

    profile = str(context.get("engine_profile") or "").strip()
    if profile:
        lines.append(f"- 项目级引擎补充说明：{profile}")

    if engine == "generic":
        lines.append(
            "- 未显式配置目标引擎时，不要默认输出 Unity 方案；请使用通用小型游戏 demo 开发视角，必要时提醒用户在项目设置或工作区中明确主引擎。"
        )
    else:
        lines.append(
            "- Design / PM / Engineering / Review 的建议、工件和评审必须优先匹配该引擎、项目工件与已配置工作区；不要在没有依据时切换到 Unity 或其他引擎。"
        )

    fragment = load_engine_prompt_fragment(engine)
    if fragment:
        lines.extend(
            [
                "",
                f"引擎专用规则片段（{label}）：",
                fragment,
            ]
        )

    return "\n".join(lines)


@lru_cache(maxsize=8)
def load_engine_prompt_fragment(engine: str) -> str:
    normalized = str(engine or "generic").strip().lower() or "generic"
    if normalized not in ENGINE_LABELS:
        normalized = "generic"

    fragment_path = REPO_ROOT / ENGINE_FRAGMENT_DIR / f"{normalized}.md"
    try:
        return fragment_path.read_text(encoding="utf-8").strip()
    except OSError:
        if normalized == "generic":
            return ""
        generic_path = REPO_ROOT / ENGINE_FRAGMENT_DIR / "generic.md"
        try:
            return generic_path.read_text(encoding="utf-8").strip()
        except OSError:
            return ""


def _infer_engine_from_project_bindings(project_id: Optional[str]) -> str:
    candidates: list[str] = []

    try:
        for workspace in list_project_workspaces(
            project_id=project_id,
            include_disabled=False,
        ):
            kind = str(workspace.get("kind") or "").strip().lower()
            if kind in ENGINE_WORKSPACE_KINDS:
                candidates.append(kind)
    except Exception:
        pass

    try:
        settings = get_project_settings(project_id=project_id)
        for connection in settings.get("mcp_connections") or []:
            if not isinstance(connection, dict) or connection.get("enabled") is False:
                continue
            engine = str(connection.get("engine") or "").strip().lower()
            if engine in ENGINE_MCP_KINDS:
                candidates.append(engine)
    except Exception:
        pass

    unique = list(dict.fromkeys(candidates))
    if len(unique) == 1:
        return unique[0]
    return ""
