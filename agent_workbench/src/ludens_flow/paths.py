from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

WORKSPACE_ENV_VAR = "LUDENS_WORKSPACE_DIR"
PROJECT_ENV_VAR = "LUDENS_PROJECT_ID"
ACTIVE_PROJECT_FILE = ".active_project"
PROJECTS_DIR_NAME = "projects"
PROJECT_META_FILE_NAME = "meta.json"
DEFAULT_PROJECT_PREFIX = "project"

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


def _read_project_meta(project_id: str) -> Dict[str, Any]:
    meta_file = get_project_meta_file(project_id)
    if not meta_file.exists():
        return {}

    try:
        return json.loads(meta_file.read_text(encoding="utf-8"))
    except Exception:
        return {}


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
    display_name = (
        meta.get("display_name") or meta.get("title") or project_id
    ).strip() or project_id
    record = {
        "id": project_id,
        "display_name": display_name,
        "title": display_name,
        "created_at": meta.get("created_at", ""),
        "updated_at": meta.get("updated_at", ""),
        "last_active_at": meta.get("last_active_at", ""),
        "last_phase": meta.get("last_phase", ""),
        "archived": _coerce_bool(meta.get("archived", False)),
        "last_message_preview": meta.get("last_message_preview", ""),
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

    meta = {
        "id": normalized,
        "display_name": chosen_name,
        "title": chosen_name,
        "created_at": existing.get("created_at") or now,
        "updated_at": now,
        "last_active_at": now if mark_active else existing.get("last_active_at", ""),
        "last_phase": existing.get("last_phase", ""),
        "archived": _coerce_bool(existing.get("archived", False)),
        "last_message_preview": existing.get("last_message_preview", ""),
    }

    if last_phase is not None:
        meta["last_phase"] = last_phase
    if archived is not None:
        meta["archived"] = bool(archived)
    if last_message_preview is not None:
        meta["last_message_preview"] = last_message_preview

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


def ensure_active_project_id() -> str:
    """确保当前总有一个激活项目。"""
    active_project = get_active_project_id()
    if active_project:
        create_project(active_project, set_active=False)
        return active_project

    projects = list_projects()
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

    create_project(normalized, set_active=False)
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
    project_id: str,
    display_name: Optional[str] = None,
    title: Optional[str] = None,
    set_active: bool = False,
    archived: Optional[bool] = None,
) -> Dict[str, Any]:
    """创建项目目录和基础元数据；已存在时刷新元数据。"""
    normalized = _normalize_project_id(project_id)
    if not normalized:
        raise ValueError("Project id is required.")

    meta = _upsert_project_meta(
        normalized,
        display_name=display_name,
        title=title,
        archived=archived,
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
    )


def list_projects() -> List[Dict[str, Any]]:
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
        projects.append(_build_project_meta_record(project_id, meta, entry))

    projects.sort(
        key=lambda item: (
            item.get("last_active_at") or item.get("updated_at") or "",
            item["id"],
        ),
        reverse=True,
    )
    return projects


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
