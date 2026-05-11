"""Capability-level project path and integration settings helpers.

This module owns non-core capability configuration that is stored inside
project metadata, such as external MCP connections and GitHub repository
bindings. Core project lifecycle, workspace lists, model routing, and agent
permission flags remain in `ludens_flow.core.paths`.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional


SUPPORTED_MCP_ENGINES = {"unity", "godot", "blender", "unreal"}
SKILL_SETTINGS_FILE = "skill_settings.json"


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(value)


def _normalize_capability_id(value: Optional[str], fallback: str) -> str:
    raw = str(value or fallback).strip()
    chars = []
    for ch in raw:
        if ch.isalnum() or ch in "._-":
            chars.append(ch.lower())
        elif ch.isspace():
            chars.append("-")
        else:
            chars.append("-")

    normalized = re.sub(r"-{2,}", "-", "".join(chars)).strip("-.")
    if not normalized:
        raise ValueError("Capability id is required.")
    return normalized


def _normalize_mcp_engine(engine: Optional[str]) -> str:
    raw = str(engine or "").strip().lower()
    if raw == "ue":
        raw = "unreal"
    if raw not in SUPPORTED_MCP_ENGINES:
        raise ValueError(
            f"Unsupported MCP engine '{raw}'. Supported engines: {', '.join(sorted(SUPPORTED_MCP_ENGINES))}."
        )
    return raw


def _normalize_mcp_connection_id(connection_id: Optional[str], fallback: str) -> str:
    return _normalize_capability_id(connection_id, fallback)


def _normalize_mcp_env(raw: Any) -> Dict[str, str]:
    if not isinstance(raw, dict):
        return {}
    env: Dict[str, str] = {}
    for key, value in raw.items():
        name = str(key or "").strip()
        if not name:
            continue
        env[name] = str(value or "")
    return env


def _normalize_mcp_args(raw: Any) -> List[str]:
    if not isinstance(raw, list):
        return []
    return [str(item) for item in raw if str(item).strip()]


def _normalize_mcp_connections(raw: Any) -> List[Dict[str, Any]]:
    if not isinstance(raw, list):
        return []

    entries: List[Dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            continue
        try:
            engine = _normalize_mcp_engine(item.get("engine"))
            connection_id = _normalize_mcp_connection_id(
                item.get("id"),
                f"{engine}-mcp",
            )
        except ValueError:
            continue

        if connection_id in seen_ids:
            connection_id = _normalize_mcp_connection_id(
                f"{connection_id}-{index + 1}",
                f"{engine}-mcp-{index + 1}",
            )
        seen_ids.add(connection_id)

        label = str(item.get("label") or "").strip() or f"{engine.title()} MCP"
        command = str(item.get("command") or "").strip()
        entries.append(
            {
                "id": connection_id,
                "engine": engine,
                "label": label,
                "command": command,
                "args": _normalize_mcp_args(item.get("args")),
                "env": _normalize_mcp_env(item.get("env")),
                "enabled": _coerce_bool(item.get("enabled", True)),
            }
        )
    return entries


def _merge_mcp_connection_lists(
    preferred: List[Dict[str, Any]], fallback: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    merged: List[Dict[str, Any]] = []
    seen_ids: set[str] = set()
    for item in [*preferred, *fallback]:
        connection_id = str(item.get("id", "") or "").strip()
        if not connection_id or connection_id in seen_ids:
            continue
        seen_ids.add(connection_id)
        merged.append(dict(item))
    return merged


def _normalize_github_repo(raw: Any) -> Dict[str, str]:
    if not isinstance(raw, dict):
        return {}
    owner = str(raw.get("owner") or "").strip()
    repo = str(raw.get("repo") or "").strip()
    if not owner or not repo:
        return {}
    result = {
        "owner": owner,
        "repo": repo.removesuffix(".git"),
    }
    url = str(raw.get("url") or "").strip()
    result["url"] = url or f"https://github.com/{result['owner']}/{result['repo']}"
    return result


def get_project_mcp_connections(project_id: Optional[str] = None) -> List[Dict[str, Any]]:
    from ludens_flow.core import paths as core_paths

    return _normalize_mcp_connections(
        core_paths.get_project_settings(project_id=project_id).get("mcp_connections")
    )


def set_project_mcp_connections(
    connections: Any,
    *,
    project_id: Optional[str] = None,
    allow_remove_mcp_connections: bool = False,
) -> Dict[str, Any]:
    from ludens_flow.core import paths as core_paths

    resolved = core_paths.resolve_project_id(project_id)
    if not resolved:
        raise ValueError("Project id is required.")

    normalized = _normalize_mcp_connections(connections)
    core_paths.touch_project(
        resolved,
        mcp_connections=normalized,
        allow_remove_mcp_connections=allow_remove_mcp_connections,
    )
    return core_paths.get_project_settings(project_id=resolved)


def get_project_github_repo(project_id: Optional[str] = None) -> Dict[str, str]:
    from ludens_flow.core import paths as core_paths

    resolved = core_paths.resolve_project_id(project_id)
    if not resolved:
        raise ValueError("Project id is required.")
    return _normalize_github_repo(core_paths._read_project_meta(resolved).get("github_repo"))


def set_project_github_repo(
    github_repo: Any, *, project_id: Optional[str] = None
) -> Dict[str, Any]:
    from ludens_flow.core import paths as core_paths

    resolved = core_paths.resolve_project_id(project_id)
    if not resolved:
        raise ValueError("Project id is required.")

    meta = core_paths.touch_project(resolved, github_repo=github_repo)
    return {
        "project_id": resolved,
        "github_repo": _normalize_github_repo(meta.get("github_repo")),
    }


def get_skills_root_dir():
    from ludens_flow.core import paths as core_paths

    return core_paths.get_workspace_root_dir() / "skills"


def get_installed_skills_dir():
    return get_skills_root_dir() / "installed"


def get_draft_skills_dir():
    return get_skills_root_dir() / "drafts"


def get_skill_install_dir(skill_id: str):
    return get_installed_skills_dir() / str(skill_id)


def get_skill_draft_dir(skill_id: str):
    return get_draft_skills_dir() / str(skill_id)


def get_project_skill_settings_file(project_id: str | None = None):
    from ludens_flow.core import paths as core_paths

    resolved = core_paths.resolve_project_id(project_id)
    if not resolved:
        raise ValueError("Project id is required.")
    return core_paths.get_project_dir(resolved) / SKILL_SETTINGS_FILE


__all__ = [
    "SKILL_SETTINGS_FILE",
    "SUPPORTED_MCP_ENGINES",
    "get_draft_skills_dir",
    "get_installed_skills_dir",
    "get_project_skill_settings_file",
    "get_project_github_repo",
    "get_project_mcp_connections",
    "get_skill_draft_dir",
    "get_skill_install_dir",
    "get_skills_root_dir",
    "set_project_github_repo",
    "set_project_mcp_connections",
]
