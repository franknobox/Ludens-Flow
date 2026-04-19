from __future__ import annotations

import json
import os
import re
import shutil
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

WORKSPACE_ENV_VAR = "LUDENS_WORKSPACE_DIR"
PROJECT_ENV_VAR = "LUDENS_PROJECT_ID"
ACTIVE_PROJECT_FILE = ".active_project"
PROJECTS_DIR_NAME = "projects"
PROJECT_META_FILE_NAME = "meta.json"
DEFAULT_PROJECT_PREFIX = "project"
PROJECT_META_SCHEMA_VERSION = 3
_UNSET = object()
DEFAULT_UNITY_WORKSPACE_ID = "unity-main"
SUPPORTED_WORKSPACE_KINDS = {"unity", "generic", "blender"}

# 统一管理仓库根目录、工作区根目录和项目级路径。
# 运行时总是落在某个项目目录下；首次启动时自动创建第一个项目。


def _discover_repo_root() -> Path:
    """从当前文件向上查找仓库根目录。"""
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / ".git").exists():
            return parent
    return current.parents[3]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(value)


def _normalize_project_id(project_id: Optional[str]) -> Optional[str]:
    if project_id is None:
        return None

    raw = str(project_id).strip()
    if not raw:
        return None

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
        raise ValueError("Project id must contain at least one valid character.")
    return normalized


def _slugify_project_name(name: Optional[str]) -> Optional[str]:
    raw = str(name or "").strip()
    if not raw:
        return None

    normalized = unicodedata.normalize("NFKD", raw)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    if ascii_only.strip():
        return _normalize_project_id(ascii_only)
    return None


def _normalize_workspace_kind(kind: Optional[str]) -> str:
    raw = str(kind or "generic").strip().lower()
    if raw not in SUPPORTED_WORKSPACE_KINDS:
        raise ValueError(
            f"Unsupported workspace kind '{raw}'. Supported kinds: {', '.join(sorted(SUPPORTED_WORKSPACE_KINDS))}."
        )
    return raw


def _normalize_workspace_id(workspace_id: Optional[str], fallback: str) -> str:
    normalized = _normalize_project_id(workspace_id or fallback)
    if not normalized:
        raise ValueError("Workspace id is required.")
    return normalized


def _default_workspace_label(kind: str) -> str:
    if kind == "unity":
        return "Unity Workspace"
    if kind == "blender":
        return "Blender Workspace"
    return "Project Workspace"


def _normalize_workspace_root(root: str, *, kind: str) -> str:
    raw = str(root or "").strip()
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in {'"', "'"}:
        raw = raw[1:-1].strip()
    if not raw:
        raise ValueError("Workspace path is required.")

    candidate = Path(raw).expanduser()
    candidate = (
        candidate.resolve()
        if candidate.is_absolute()
        else (Path.cwd() / candidate).resolve()
    )

    if not candidate.exists() or not candidate.is_dir():
        raise ValueError(f"Workspace path does not exist or is not a directory: {candidate}")

    if kind == "unity":
        assets_dir = candidate / "Assets"
        project_settings_dir = candidate / "ProjectSettings"
        if not assets_dir.exists() or not project_settings_dir.exists():
            raise ValueError(
                "Unity workspace must contain both 'Assets' and 'ProjectSettings' directories."
            )

    return str(candidate)


def _build_workspace_entry(
    *,
    root: str,
    kind: str = "generic",
    workspace_id: Optional[str] = None,
    label: Optional[str] = None,
    writable: bool = False,
    enabled: bool = True,
    source: str = "user",
) -> Dict[str, Any]:
    normalized_kind = _normalize_workspace_kind(kind)
    normalized_root = _normalize_workspace_root(root, kind=normalized_kind)
    normalized_id = _normalize_workspace_id(
        workspace_id, f"{normalized_kind}-workspace"
    )
    display_label = str(label or "").strip() or _default_workspace_label(normalized_kind)
    return {
        "id": normalized_id,
        "label": display_label,
        "kind": normalized_kind,
        "root": normalized_root,
        "writable": _coerce_bool(writable),
        "enabled": _coerce_bool(enabled),
        "source": str(source or "user").strip() or "user",
    }


def _legacy_workspace_entry_from_root(root: str) -> Dict[str, Any]:
    candidate = Path(str(root or "")).expanduser()
    resolved_root = (
        candidate.resolve() if candidate.is_absolute() else (Path.cwd() / candidate).resolve()
    )
    return {
        "id": DEFAULT_UNITY_WORKSPACE_ID,
        "label": "Unity Project",
        "kind": "unity",
        "root": str(resolved_root),
        "writable": False,
        "enabled": True,
        "source": "legacy",
    }


def _normalize_workspace_list(raw_workspaces: Any, legacy_unity_root: str = "") -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    seen_ids: set[str] = set()

    if isinstance(raw_workspaces, list):
        for index, item in enumerate(raw_workspaces):
            if not isinstance(item, dict):
                continue
            try:
                raw_root = str(item.get("root", "") or "").strip()
                if not raw_root:
                    continue
                normalized_kind = _normalize_workspace_kind(
                    str(item.get("kind", "generic") or "generic")
                )
                candidate = Path(raw_root).expanduser()
                resolved_root = (
                    candidate.resolve()
                    if candidate.is_absolute()
                    else (Path.cwd() / candidate).resolve()
                )
                entry = {
                    "id": _normalize_workspace_id(
                        str(item.get("id", "") or f"workspace-{index + 1}"),
                        f"workspace-{index + 1}",
                    ),
                    "label": str(item.get("label", "") or "").strip()
                    or _default_workspace_label(normalized_kind),
                    "kind": normalized_kind,
                    "root": str(resolved_root),
                    "writable": _coerce_bool(item.get("writable", False)),
                    "enabled": _coerce_bool(item.get("enabled", True)),
                    "source": str(item.get("source", "user") or "user").strip()
                    or "user",
                }
            except Exception:
                continue
            if entry["id"] in seen_ids:
                continue
            seen_ids.add(entry["id"])
            entries.append(entry)

    if not entries and str(legacy_unity_root or "").strip():
        legacy_entry = _legacy_workspace_entry_from_root(legacy_unity_root)
        entries.append(legacy_entry)

    return entries


def _first_workspace_root(
    workspaces: List[Dict[str, Any]], *, kind: Optional[str] = None
) -> str:
    for workspace in workspaces:
        if kind and workspace.get("kind") != kind:
            continue
        if not _coerce_bool(workspace.get("enabled", True)):
            continue
        return str(workspace.get("root", "") or "")
    return ""


def _read_project_meta(project_id: str) -> Dict[str, Any]:
    meta_file = get_project_meta_file(project_id)
    if not meta_file.exists():
        return {}

    try:
        raw = json.loads(meta_file.read_text(encoding="utf-8"))
        migrated, changed, source_version = _migrate_project_meta_payload(
            project_id, raw
        )
        if changed:
            _write_project_meta(project_id, migrated)
            if source_version != PROJECT_META_SCHEMA_VERSION:
                from ludens_flow.core.state.state_logs import write_audit_log

                write_audit_log(
                    event="PROJECT_META_SCHEMA_MIGRATION",
                    detail=(f"from={source_version} to={PROJECT_META_SCHEMA_VERSION}"),
                    project_id=project_id,
                )
        return migrated
    except Exception:
        return {}


def _migrate_project_meta_payload(
    project_id: str, raw_meta: Dict[str, Any]
) -> tuple[Dict[str, Any], bool, int]:
    meta = dict(raw_meta or {})

    raw_version = meta.get("schema_version", 1)
    try:
        source_version = int(raw_version)
    except (TypeError, ValueError):
        source_version = 1

    now = _now_iso()
    display_name = (
        str(meta.get("display_name") or meta.get("title") or project_id).strip()
        or project_id
    )

    normalized_id = project_id
    try:
        candidate_id = _normalize_project_id(str(meta.get("id") or project_id))
        if candidate_id:
            normalized_id = candidate_id
    except Exception:
        normalized_id = project_id

    workspaces = _normalize_workspace_list(
        meta.get("workspaces"),
        legacy_unity_root=str(meta.get("unity_root", "") or ""),
    )

    migrated = {
        "schema_version": PROJECT_META_SCHEMA_VERSION,
        "id": normalized_id,
        "display_name": display_name,
        "title": str(meta.get("title") or display_name).strip() or display_name,
        "created_at": meta.get("created_at", "") or now,
        "updated_at": meta.get("updated_at", "") or now,
        "last_active_at": meta.get("last_active_at", ""),
        "last_phase": meta.get("last_phase", ""),
        "archived": _coerce_bool(meta.get("archived", False)),
        "last_message_preview": str(meta.get("last_message_preview", "") or ""),
        "agent_file_write_enabled": _coerce_bool(
            meta.get("agent_file_write_enabled", True)
        ),
        "unity_root": _first_workspace_root(workspaces, kind="unity"),
        "workspaces": workspaces,
    }

    changed = source_version != PROJECT_META_SCHEMA_VERSION or any(
        migrated.get(key) != meta.get(key) for key in migrated.keys()
    )
    return migrated, changed, source_version


def _write_project_meta(project_id: str, meta: Dict[str, Any]) -> Dict[str, Any]:
    meta_file = get_project_meta_file(project_id)
    meta_file.parent.mkdir(parents=True, exist_ok=True)
    meta_file.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return meta


def _build_project_meta_record(
    project_id: str, meta: Dict[str, Any], project_dir: Optional[Path] = None
) -> Dict[str, Any]:
    workspaces = _normalize_workspace_list(
        meta.get("workspaces"),
        legacy_unity_root=str(meta.get("unity_root", "") or ""),
    )
    display_name = (
        meta.get("display_name") or meta.get("title") or project_id
    ).strip() or project_id
    record = {
        "schema_version": meta.get("schema_version", PROJECT_META_SCHEMA_VERSION),
        "id": project_id,
        "display_name": display_name,
        "title": display_name,
        "created_at": meta.get("created_at", ""),
        "updated_at": meta.get("updated_at", ""),
        "last_active_at": meta.get("last_active_at", ""),
        "last_phase": meta.get("last_phase", ""),
        "archived": _coerce_bool(meta.get("archived", False)),
        "last_message_preview": meta.get("last_message_preview", ""),
        "agent_file_write_enabled": _coerce_bool(
            meta.get("agent_file_write_enabled", True)
        ),
        "unity_root": _first_workspace_root(workspaces, kind="unity"),
        "workspaces": workspaces,
    }
    if project_dir is not None:
        record["path"] = str(project_dir)
    return record


def _upsert_project_meta(
    project_id: str,
    *,
    display_name: Optional[str] = None,
    title: Optional[str] = None,
    mark_active: bool = False,
    last_phase: Optional[str] = None,
    archived: Optional[bool] = None,
    last_message_preview: Optional[str] = None,
    agent_file_write_enabled: Any = _UNSET,
    unity_root: Any = _UNSET,
    workspaces: Any = _UNSET,
) -> Dict[str, Any]:
    normalized = _normalize_project_id(project_id)
    if not normalized:
        raise ValueError("Project id is required.")

    project_dir = get_projects_dir() / normalized
    project_dir.mkdir(parents=True, exist_ok=True)

    existing = _read_project_meta(normalized)
    now = _now_iso()
    chosen_name = (
        display_name
        or title
        or existing.get("display_name")
        or existing.get("title")
        or normalized
    ).strip() or normalized

    existing_workspaces = _normalize_workspace_list(
        existing.get("workspaces"),
        legacy_unity_root=str(existing.get("unity_root", "") or ""),
    )

    meta = {
        "schema_version": PROJECT_META_SCHEMA_VERSION,
        "id": normalized,
        "display_name": chosen_name,
        "title": chosen_name,
        "created_at": existing.get("created_at") or now,
        "updated_at": now,
        "last_active_at": now if mark_active else existing.get("last_active_at", ""),
        "last_phase": existing.get("last_phase", ""),
        "archived": _coerce_bool(existing.get("archived", False)),
        "last_message_preview": existing.get("last_message_preview", ""),
        "agent_file_write_enabled": _coerce_bool(
            existing.get("agent_file_write_enabled", True)
        ),
        "unity_root": _first_workspace_root(existing_workspaces, kind="unity"),
        "workspaces": existing_workspaces,
    }

    if last_phase is not None:
        meta["last_phase"] = last_phase
    if archived is not None:
        meta["archived"] = bool(archived)
    if last_message_preview is not None:
        meta["last_message_preview"] = last_message_preview
    if agent_file_write_enabled is not _UNSET:
        meta["agent_file_write_enabled"] = _coerce_bool(agent_file_write_enabled)
    if unity_root is not _UNSET:
        if str(unity_root or "").strip():
            next_workspaces = [
                workspace
                for workspace in meta["workspaces"]
                if workspace.get("id") != DEFAULT_UNITY_WORKSPACE_ID
            ]
            next_workspaces.insert(
                0,
                _build_workspace_entry(
                    root=str(unity_root),
                    kind="unity",
                    workspace_id=DEFAULT_UNITY_WORKSPACE_ID,
                    label="Unity Project",
                    writable=False,
                    enabled=True,
                    source="legacy-api",
                ),
            )
            meta["workspaces"] = next_workspaces
        else:
            meta["workspaces"] = [
                workspace
                for workspace in meta["workspaces"]
                if workspace.get("kind") != "unity"
            ]
        meta["unity_root"] = _first_workspace_root(meta["workspaces"], kind="unity")
    if workspaces is not _UNSET:
        normalized_workspaces = _normalize_workspace_list(workspaces)
        meta["workspaces"] = normalized_workspaces
        meta["unity_root"] = _first_workspace_root(normalized_workspaces, kind="unity")

    stored = _write_project_meta(normalized, meta)
    return _build_project_meta_record(normalized, stored, project_dir)


REPO_ROOT = _discover_repo_root()
AGENT_WORKBENCH_ROOT = REPO_ROOT / "agent_workbench"


def get_workspace_root_dir() -> Path:
    """返回工作区根目录。"""
    override = os.getenv(WORKSPACE_ENV_VAR)
    if override:
        return Path(override).expanduser().resolve()
    return REPO_ROOT / "workspace"


def get_projects_dir() -> Path:
    return get_workspace_root_dir() / PROJECTS_DIR_NAME


def get_project_meta_file(project_id: str) -> Path:
    normalized = _normalize_project_id(project_id)
    if not normalized:
        raise ValueError("Project id is required.")
    return get_projects_dir() / normalized / PROJECT_META_FILE_NAME


def get_active_project_id() -> Optional[str]:
    """返回当前激活项目；优先环境变量，其次根工作区中的活动项目文件。"""
    env_project = _normalize_project_id(os.getenv(PROJECT_ENV_VAR))
    if env_project:
        return env_project

    active_file = get_workspace_root_dir() / ACTIVE_PROJECT_FILE
    if not active_file.exists():
        return None

    raw = active_file.read_text(encoding="utf-8").strip()
    return _normalize_project_id(raw)


def _next_project_id() -> str:
    existing = {item["id"] for item in list_projects()}
    index = 1
    while True:
        candidate = f"{DEFAULT_PROJECT_PREFIX}-{index}"
        if candidate not in existing:
            return candidate
        index += 1


def next_project_id(display_name: Optional[str] = None) -> str:
    candidate = _slugify_project_name(display_name)
    if candidate:
        existing = {item["id"] for item in list_projects(include_archived=True)}
        if candidate not in existing:
            return candidate

        suffix = 2
        while f"{candidate}-{suffix}" in existing:
            suffix += 1
        return f"{candidate}-{suffix}"

    return _next_project_id()


def ensure_active_project_id() -> str:
    """确保当前总有一个激活项目。"""
    active_project = get_active_project_id()
    if active_project:
        meta = create_project(active_project, set_active=False)
        if not meta.get("archived", False):
            return active_project

    projects = list_projects(include_archived=False)
    if projects:
        latest = projects[0]["id"]
        set_active_project_id(latest)
        return latest

    first_project = _next_project_id()
    create_project(first_project, set_active=True)
    return first_project


def set_active_project_id(project_id: Optional[str]) -> Optional[str]:
    """设置当前激活项目；传入空值时清除激活状态。"""
    active_file = get_workspace_root_dir() / ACTIVE_PROJECT_FILE
    active_file.parent.mkdir(parents=True, exist_ok=True)

    normalized = _normalize_project_id(project_id)
    if not normalized:
        active_file.unlink(missing_ok=True)
        return None

    meta = create_project(normalized, set_active=False)
    if meta.get("archived", False):
        raise ValueError(f"Cannot activate archived project: {normalized}")
    active_file.write_text(normalized, encoding="utf-8")
    touch_project(normalized, mark_active=True)
    return normalized


def resolve_project_id(project_id: Optional[str] = None) -> Optional[str]:
    """解析显式 project_id 或当前激活项目。"""
    explicit = _normalize_project_id(project_id)
    if explicit:
        return explicit
    return ensure_active_project_id()


def get_project_dir(project_id: Optional[str] = None) -> Path:
    """返回项目目录。"""
    resolved = resolve_project_id(project_id)
    if not resolved:
        raise ValueError("Project id is required.")
    return get_projects_dir() / resolved


def get_workspace_dir(project_id: Optional[str] = None) -> Path:
    """兼容旧接口：返回当前项目目录。"""
    return get_project_dir(project_id)


def create_project(
    project_id: Optional[str] = None,
    display_name: Optional[str] = None,
    title: Optional[str] = None,
    set_active: bool = False,
    archived: Optional[bool] = None,
    agent_file_write_enabled: Any = _UNSET,
    unity_root: Any = _UNSET,
    workspaces: Any = _UNSET,
) -> Dict[str, Any]:
    """创建项目目录和基础元数据；已存在时刷新元数据。"""
    normalized = _normalize_project_id(project_id) or next_project_id(display_name or title)
    if not normalized:
        raise ValueError("Project id is required.")

    meta = _upsert_project_meta(
        normalized,
        display_name=display_name,
        title=title,
        archived=archived,
        agent_file_write_enabled=agent_file_write_enabled,
        unity_root=unity_root,
        workspaces=workspaces,
    )

    if set_active:
        set_active_project_id(normalized)

    return meta


def touch_project(
    project_id: str,
    display_name: Optional[str] = None,
    title: Optional[str] = None,
    mark_active: bool = False,
    last_phase: Optional[str] = None,
    archived: Optional[bool] = None,
    last_message_preview: Optional[str] = None,
    agent_file_write_enabled: Any = _UNSET,
    unity_root: Any = _UNSET,
    workspaces: Any = _UNSET,
) -> Dict[str, Any]:
    """刷新项目元数据，用于记录最近活跃时间。"""
    normalized = _normalize_project_id(project_id)
    if not normalized:
        raise ValueError("Project id is required.")

    return _upsert_project_meta(
        normalized,
        display_name=display_name,
        title=title,
        mark_active=mark_active,
        last_phase=last_phase,
        archived=archived,
        last_message_preview=last_message_preview,
        agent_file_write_enabled=agent_file_write_enabled,
        unity_root=unity_root,
        workspaces=workspaces,
    )


def list_project_workspaces(
    project_id: Optional[str] = None,
    *,
    kind: Optional[str] = None,
    include_disabled: bool = True,
) -> List[Dict[str, Any]]:
    resolved = resolve_project_id(project_id)
    if not resolved:
        return []
    meta = _read_project_meta(resolved)
    requested_kind = _normalize_workspace_kind(kind) if kind else None
    workspaces = _normalize_workspace_list(
        meta.get("workspaces"),
        legacy_unity_root=str(meta.get("unity_root", "") or ""),
    )
    results: List[Dict[str, Any]] = []
    for workspace in workspaces:
        if requested_kind and workspace.get("kind") != requested_kind:
            continue
        if not include_disabled and not _coerce_bool(workspace.get("enabled", True)):
            continue
        results.append(dict(workspace))
    return results


def get_project_workspace(
    project_id: Optional[str] = None,
    *,
    workspace_id: Optional[str] = None,
    kind: Optional[str] = None,
    require_enabled: bool = True,
) -> Optional[Dict[str, Any]]:
    requested_id = _normalize_project_id(workspace_id) if workspace_id else None
    requested_kind = _normalize_workspace_kind(kind) if kind else None
    for workspace in list_project_workspaces(project_id=project_id, include_disabled=True):
        if requested_id and workspace.get("id") != requested_id:
            continue
        if requested_kind and workspace.get("kind") != requested_kind:
            continue
        if require_enabled and not _coerce_bool(workspace.get("enabled", True)):
            continue
        return workspace
    return None


def add_project_workspace(
    root: str,
    *,
    project_id: Optional[str] = None,
    kind: str = "generic",
    workspace_id: Optional[str] = None,
    label: Optional[str] = None,
    writable: bool = False,
    enabled: bool = True,
) -> Dict[str, Any]:
    resolved = resolve_project_id(project_id)
    normalized_kind = _normalize_workspace_kind(kind)
    desired_id = _normalize_workspace_id(
        workspace_id, f"{normalized_kind}-workspace"
    )
    existing = [
        workspace
        for workspace in list_project_workspaces(resolved, include_disabled=True)
        if workspace.get("id") != desired_id
    ]
    entry = _build_workspace_entry(
        root=root,
        kind=normalized_kind,
        workspace_id=desired_id,
        label=label,
        writable=writable,
        enabled=enabled,
        source="user",
    )
    existing.append(entry)
    meta = touch_project(resolved, workspaces=existing)
    from ludens_flow.core.state.state_logs import write_audit_log

    write_audit_log(
        event="PROJECT_WORKSPACE_UPSERT",
        detail=(
            f"workspace_id={entry['id']} kind={entry['kind']} "
            f"writable={entry['writable']} enabled={entry['enabled']} root={entry['root']}"
        ),
        project_id=resolved,
    )
    return meta


def remove_project_workspace(
    workspace_id: str,
    *,
    project_id: Optional[str] = None,
) -> Dict[str, Any]:
    resolved = resolve_project_id(project_id)
    target_id = _normalize_workspace_id(workspace_id, "workspace")
    existing = list_project_workspaces(resolved, include_disabled=True)
    target = next((workspace for workspace in existing if workspace.get("id") == target_id), None)
    if target is None:
        raise FileNotFoundError(f"Workspace not found: {target_id}")

    remaining = [workspace for workspace in existing if workspace.get("id") != target_id]
    meta = touch_project(resolved, workspaces=remaining)
    from ludens_flow.core.state.state_logs import write_audit_log

    write_audit_log(
        event="PROJECT_WORKSPACE_REMOVED",
        detail=f"workspace_id={target_id} kind={target.get('kind', '')} root={target.get('root', '')}",
        project_id=resolved,
    )
    return meta


def get_project_settings(project_id: Optional[str] = None) -> Dict[str, Any]:
    resolved = resolve_project_id(project_id)
    if not resolved:
        raise ValueError("Project id is required.")

    record = _build_project_meta_record(
        resolved,
        _read_project_meta(resolved),
        get_project_dir(resolved),
    )
    return {
        "project_id": resolved,
        "agent_file_write_enabled": _coerce_bool(
            record.get("agent_file_write_enabled", True)
        ),
    }


def get_project_agent_file_write_enabled(project_id: Optional[str] = None) -> bool:
    return _coerce_bool(
        get_project_settings(project_id=project_id).get(
            "agent_file_write_enabled", True
        )
    )


def set_project_agent_file_write_enabled(
    enabled: bool, *, project_id: Optional[str] = None
) -> Dict[str, Any]:
    resolved = resolve_project_id(project_id)
    if not resolved:
        raise ValueError("Project id is required.")
    meta = touch_project(
        resolved,
        agent_file_write_enabled=_coerce_bool(enabled),
    )
    return {
        "project_id": resolved,
        "agent_file_write_enabled": _coerce_bool(
            meta.get("agent_file_write_enabled", True)
        ),
    }


def set_project_unity_root(
    unity_root: str, project_id: Optional[str] = None
) -> Dict[str, Any]:
    return add_project_workspace(
        unity_root,
        project_id=project_id,
        kind="unity",
        workspace_id=DEFAULT_UNITY_WORKSPACE_ID,
        label="Unity Project",
        writable=False,
        enabled=True,
    )


def clear_project_unity_root(project_id: Optional[str] = None) -> Dict[str, Any]:
    resolved = resolve_project_id(project_id)
    existing = list_project_workspaces(resolved, include_disabled=True)
    removed = [
        workspace
        for workspace in existing
        if workspace.get("kind") == "unity"
        and workspace.get("id") == DEFAULT_UNITY_WORKSPACE_ID
    ]
    remaining = [
        workspace
        for workspace in existing
        if not (
            workspace.get("kind") == "unity"
            and workspace.get("id") == DEFAULT_UNITY_WORKSPACE_ID
        )
    ]
    meta = touch_project(resolved, workspaces=remaining)
    if removed:
        from ludens_flow.core.state.state_logs import write_audit_log

        write_audit_log(
            event="PROJECT_WORKSPACE_REMOVED",
            detail=(
                "workspace_id="
                f"{DEFAULT_UNITY_WORKSPACE_ID} kind=unity "
                f"root={removed[0].get('root', '')}"
            ),
            project_id=resolved,
        )
    return meta


def get_project_unity_root(project_id: Optional[str] = None) -> Optional[str]:
    workspace = get_project_workspace(project_id, kind="unity", require_enabled=True)
    if not workspace:
        return None
    root = str(workspace.get("root", "")).strip()
    return root or None


def list_projects(*, include_archived: bool = True) -> List[Dict[str, Any]]:
    """扫描多项目目录并返回项目元数据列表。"""
    projects_dir = get_projects_dir()
    if not projects_dir.exists():
        return []

    projects: List[Dict[str, Any]] = []
    for entry in projects_dir.iterdir():
        if not entry.is_dir():
            continue
        project_id = _normalize_project_id(entry.name)
        if not project_id:
            continue
        meta = _read_project_meta(project_id)
        record = _build_project_meta_record(project_id, meta, entry)
        if not include_archived and record.get("archived", False):
            continue
        projects.append(record)

    projects.sort(
        key=lambda item: (
            item.get("last_active_at") or item.get("updated_at") or "",
            item["id"],
        ),
        reverse=True,
    )
    return projects


def list_active_projects() -> List[Dict[str, Any]]:
    return list_projects(include_archived=False)


def list_archived_projects() -> List[Dict[str, Any]]:
    return [item for item in list_projects(include_archived=True) if item.get("archived")]


def archive_project(project_id: str) -> Dict[str, Any]:
    normalized = _normalize_project_id(project_id)
    if not normalized:
        raise ValueError("Project id is required.")

    meta = create_project(normalized, set_active=False)
    if meta.get("archived", False):
        return meta

    archived_meta = touch_project(normalized, archived=True)
    if get_active_project_id() == normalized:
        remaining = [
            item for item in list_active_projects() if item["id"] != normalized
        ]
        if remaining:
            set_active_project_id(remaining[0]["id"])
        else:
            set_active_project_id(_next_project_id())
    return archived_meta


def restore_project(project_id: str, *, set_active: bool = False) -> Dict[str, Any]:
    normalized = _normalize_project_id(project_id)
    if not normalized:
        raise ValueError("Project id is required.")

    create_project(normalized, set_active=False)
    restored_meta = touch_project(normalized, archived=False)
    if set_active:
        set_active_project_id(normalized)
    return restored_meta


def rename_project(project_id: str, display_name: str) -> Dict[str, Any]:
    normalized = _normalize_project_id(project_id)
    if not normalized:
        raise ValueError("Project id is required.")

    if not _read_project_meta(normalized):
        raise FileNotFoundError(f"Project not found: {normalized}")

    cleaned_name = str(display_name or "").strip()
    if not cleaned_name:
        raise ValueError("Display name is required.")

    return touch_project(normalized, display_name=cleaned_name, title=cleaned_name)


def delete_project(project_id: str) -> str:
    normalized = _normalize_project_id(project_id)
    if not normalized:
        raise ValueError("Project id is required.")

    meta = _read_project_meta(normalized)
    if not meta:
        raise FileNotFoundError(f"Project not found: {normalized}")
    if not _coerce_bool(meta.get("archived", False)):
        raise RuntimeError(
            f"Project '{normalized}' must be archived before it can be deleted."
        )
    if get_active_project_id() == normalized:
        raise RuntimeError(f"Cannot delete active project '{normalized}'.")

    project_dir = get_project_dir(normalized)
    if project_dir.exists():
        shutil.rmtree(project_dir, ignore_errors=False)
    return normalized


def get_logs_dir(project_id: Optional[str] = None) -> Path:
    return get_project_dir(project_id) / "logs"


def get_memory_dir(project_id: Optional[str] = None) -> Path:
    return get_project_dir(project_id) / "memory"


def get_images_dir(project_id: Optional[str] = None) -> Path:
    return get_project_dir(project_id) / "images"


def get_dev_notes_dir(project_id: Optional[str] = None) -> Path:
    return get_project_dir(project_id) / "dev_notes"


def get_patches_dir(project_id: Optional[str] = None) -> Path:
    return get_project_dir(project_id) / "patches"


def get_state_file(project_id: Optional[str] = None) -> Path:
    return get_project_dir(project_id) / "state.json"


def get_artifact_paths(project_id: Optional[str] = None) -> Dict[str, Path]:
    """返回核心工件到物理文件路径的映射表。"""
    workspace_dir = get_project_dir(project_id)
    dev_notes_dir = get_dev_notes_dir(project_id)
    return {
        "gdd": workspace_dir / "GDD.md",
        "pm": workspace_dir / "PROJECT_PLAN.md",
        "eng": workspace_dir / "IMPLEMENTATION_PLAN.md",
        "review": workspace_dir / "REVIEW_REPORT.md",
        "devlog": dev_notes_dir / "DEVLOG.md",
    }
