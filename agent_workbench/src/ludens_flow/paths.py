from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

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
    return datetime.utcnow().isoformat() + "Z"


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


def _read_project_meta(project_id: str) -> Dict[str, str]:
    meta_file = get_project_meta_file(project_id)
    if not meta_file.exists():
        return {}

    try:
        return json.loads(meta_file.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_project_meta(project_id: str, meta: Dict[str, str]) -> Dict[str, str]:
    meta_file = get_project_meta_file(project_id)
    meta_file.parent.mkdir(parents=True, exist_ok=True)
    meta_file.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return meta


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


def create_project(project_id: str, title: Optional[str] = None, set_active: bool = False) -> Dict[str, str]:
    """创建项目目录和基础元数据；已存在时刷新元数据。"""
    normalized = _normalize_project_id(project_id)
    if not normalized:
        raise ValueError("Project id is required.")

    project_dir = get_project_dir(normalized)
    project_dir.mkdir(parents=True, exist_ok=True)

    now = _now_iso()
    existing = _read_project_meta(normalized)
    meta = {
        "id": normalized,
        "title": title or existing.get("title") or normalized,
        "created_at": existing.get("created_at") or now,
        "updated_at": now,
        "last_active_at": existing.get("last_active_at") or "",
    }
    _write_project_meta(normalized, meta)

    if set_active:
        set_active_project_id(normalized)

    return meta


def touch_project(project_id: str, title: Optional[str] = None, mark_active: bool = False) -> Dict[str, str]:
    """刷新项目元数据，用于记录最近活跃时间。"""
    normalized = _normalize_project_id(project_id)
    if not normalized:
        raise ValueError("Project id is required.")

    meta = create_project(normalized, title=title, set_active=False)
    now = _now_iso()
    meta["updated_at"] = now
    if title:
        meta["title"] = title
    if mark_active:
        meta["last_active_at"] = now
    return _write_project_meta(normalized, meta)


def list_projects() -> List[Dict[str, str]]:
    """扫描多项目目录并返回项目元数据列表。"""
    projects_dir = get_projects_dir()
    if not projects_dir.exists():
        return []

    projects: List[Dict[str, str]] = []
    for entry in projects_dir.iterdir():
        if not entry.is_dir():
            continue
        project_id = _normalize_project_id(entry.name)
        if not project_id:
            continue
        meta = _read_project_meta(project_id)
        projects.append(
            {
                "id": project_id,
                "title": meta.get("title", project_id),
                "created_at": meta.get("created_at", ""),
                "updated_at": meta.get("updated_at", ""),
                "last_active_at": meta.get("last_active_at", ""),
                "path": str(entry),
            }
        )

    projects.sort(key=lambda item: (item.get("last_active_at", ""), item["id"]), reverse=True)
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
