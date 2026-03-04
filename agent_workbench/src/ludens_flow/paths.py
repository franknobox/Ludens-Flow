from __future__ import annotations

import os
from pathlib import Path
from typing import Dict

WORKSPACE_ENV_VAR = "LUDENS_WORKSPACE_DIR"


def _discover_repo_root() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / ".git").exists():
            return parent
    return current.parents[3]


REPO_ROOT = _discover_repo_root()
AGENT_WORKBENCH_ROOT = REPO_ROOT / "agent_workbench"


def get_workspace_dir() -> Path:
    override = os.getenv(WORKSPACE_ENV_VAR)
    if override:
        return Path(override).expanduser().resolve()
    return REPO_ROOT / "workspace"


def get_logs_dir() -> Path:
    return get_workspace_dir() / "logs"


def get_memory_dir() -> Path:
    return get_workspace_dir() / "memory"


def get_dev_notes_dir() -> Path:
    return get_workspace_dir() / "dev_notes"


def get_patches_dir() -> Path:
    return get_workspace_dir() / "patches"


def get_state_file() -> Path:
    return get_workspace_dir() / "state.json"


def get_artifact_paths() -> Dict[str, Path]:
    workspace_dir = get_workspace_dir()
    dev_notes_dir = get_dev_notes_dir()
    return {
        "gdd": workspace_dir / "GDD.md",
        "pm": workspace_dir / "PROJECT_PLAN.md",
        "eng": workspace_dir / "IMPLEMENTATION_PLAN.md",
        "review": workspace_dir / "REVIEW_REPORT.md",
        "devlog": dev_notes_dir / "DEVLOG.md",
    }
