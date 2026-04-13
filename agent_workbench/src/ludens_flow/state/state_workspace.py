import shutil
from pathlib import Path
from typing import Optional

from ludens_flow.paths import (
    create_project,
    get_artifact_paths,
    get_dev_notes_dir,
    get_images_dir,
    get_logs_dir,
    get_memory_dir,
    get_patches_dir,
    get_project_dir,
    get_workspace_dir,
    get_workspace_root_dir,
    resolve_project_id,
    touch_project,
)

from .state_models import LudensState

# 旧版单项目文件映射：迁移到 project-1 时复用。
LEGACY_ROOT_FILES = {
    "state.json": "state.json",
    "USER_PROFILE.md": "USER_PROFILE.md",
    "GDD.md": "GDD.md",
    "PROJECT_PLAN.md": "PROJECT_PLAN.md",
    "IMPLEMENTATION_PLAN.md": "IMPLEMENTATION_PLAN.md",
    "REVIEW_REPORT.md": "REVIEW_REPORT.md",
}

# 旧版单项目目录映射：迁移到 project-1 时复用。
LEGACY_ROOT_DIRS = {
    "logs": "logs",
    "memory": "memory",
    "images": "images",
    "dev_notes": "dev_notes",
    "patches": "patches",
}


# 判断路径是否已有有效内容，避免迁移覆盖现有数据。
def _has_content(path: Path) -> bool:
    if not path.exists():
        return False
    if path.is_dir():
        return any(path.iterdir())
    return path.stat().st_size > 0


# 执行单个旧路径迁移，目标有内容时直接跳过。
def _move_legacy_entry(source: Path, target: Path) -> bool:
    if not source.exists():
        return False
    if _has_content(target):
        return False

    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if target.is_dir():
            shutil.rmtree(target, ignore_errors=True)
        else:
            target.unlink(missing_ok=True)

    shutil.move(str(source), str(target))
    return True


# 仅在 project-1 首次运行时搬迁历史单项目数据。
def migrate_legacy_workspace_to_project(project_id: Optional[str] = None) -> list[str]:
    """Move legacy single-project workspace files into project-1 once."""
    resolved = resolve_project_id(project_id)
    if resolved != "project-1":
        return []

    workspace_root = get_workspace_root_dir()
    project_dir = get_project_dir(resolved)
    moved: list[str] = []

    for legacy_name, target_name in LEGACY_ROOT_FILES.items():
        if _move_legacy_entry(workspace_root / legacy_name, project_dir / target_name):
            moved.append(legacy_name)

    for legacy_name, target_name in LEGACY_ROOT_DIRS.items():
        if _move_legacy_entry(workspace_root / legacy_name, project_dir / target_name):
            moved.append(legacy_name)

    return moved


# 初始化项目工作区：保证目录和工件空文件齐备。
def init_workspace(project_id: Optional[str] = None) -> None:
    """初始化运行工作区，确保必备目录与空文件存在"""
    resolved = resolve_project_id(project_id)
    if resolved:
        create_project(resolved)
        migrate_legacy_workspace_to_project(resolved)
        touch_project(resolved)

    workspace_dir = get_workspace_dir(resolved)
    logs_dir = get_logs_dir(resolved)
    memory_dir = get_memory_dir(resolved)
    images_dir = get_images_dir(resolved)
    dev_notes_dir = get_dev_notes_dir(resolved)
    patches_dir = get_patches_dir(resolved)
    artifact_paths = get_artifact_paths(resolved)

    for directory in [
        workspace_dir,
        logs_dir,
        memory_dir,
        images_dir,
        dev_notes_dir,
        patches_dir,
    ]:
        directory.mkdir(parents=True, exist_ok=True)

    for path in artifact_paths.values():
        if not path.exists():
            path.touch()


# 清空图片缓存目录，保留目录本身。
def clear_images_dir(project_id: Optional[str] = None) -> Path:
    """Delete all files/subdirectories under workspace/images and keep the folder."""
    images_dir = get_images_dir(resolve_project_id(project_id))
    images_dir.mkdir(parents=True, exist_ok=True)

    for entry in images_dir.iterdir():
        if entry.is_dir():
            shutil.rmtree(entry, ignore_errors=True)
        else:
            entry.unlink(missing_ok=True)
    return images_dir


# 清空所有 canonical 工件，并清理 dev_notes/patches。
def _clear_artifact_files(project_id: Optional[str] = None) -> None:
    """将所有工件文件清空（重置为空文件），并清理 dev_notes 和 patches 目录。"""
    resolved = resolve_project_id(project_id)
    artifact_paths = get_artifact_paths(resolved)
    for path in artifact_paths.values():
        if path.exists():
            path.write_text("", encoding="utf-8")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch()

    for directory in [get_dev_notes_dir(resolved), get_patches_dir(resolved)]:
        if directory.exists():
            for entry in directory.iterdir():
                if entry.is_dir():
                    shutil.rmtree(entry, ignore_errors=True)
                else:
                    entry.unlink(missing_ok=True)


# 项目级 reset 入口：委托给 StateStore 统一处理。
def reset_current_project_state(
    clear_images: bool = True, project_id: Optional[str] = None
) -> LudensState:
    """Reset one project's persisted state, artifacts and optional image cache."""
    from .state_store import get_state_store

    return get_state_store().reset(clear_images=clear_images, project_id=project_id)


# 兼容旧调用名，行为与 reset_current_project_state 一致。
def reset_workspace_state(
    clear_images: bool = True, project_id: Optional[str] = None
) -> LudensState:
    """Compatibility alias for older callers."""
    return reset_current_project_state(clear_images=clear_images, project_id=project_id)
