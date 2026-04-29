"""
文件功能：状态子模块（state_workspace.py），服务项目级状态持久化与演进。
核心内容：围绕状态读写、迁移、日志与项目工作区操作提供基础能力。
核心内容：与 graph/router 协同，保证流程状态可追踪、可恢复、可扩展。
"""

import json
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Union

from ludens_flow.core.paths import (
    PROJECT_META_FILE_NAME,
    create_project,
    get_artifact_paths,
    get_dev_notes_dir,
    get_images_dir,
    get_logs_dir,
    get_project_meta_file,
    get_memory_dir,
    get_patches_dir,
    get_project_dir,
    get_workspace_dir,
    get_workspace_root_dir,
    get_state_file,
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

    if moved:
        from .state_logs import write_audit_log

        write_audit_log(
            event="WORKSPACE_MIGRATION",
            detail=f"moved_legacy_entries={','.join(moved)}",
            project_id=resolved,
        )

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


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def export_project_bundle(
    output_path: Union[str, Path], project_id: Optional[str] = None
) -> Path:
    """Export one project's state and artifacts as a zip bundle."""
    resolved = resolve_project_id(project_id)
    project_dir = get_project_dir(resolved)
    if not project_dir.exists():
        raise FileNotFoundError(f"Project directory not found: {project_dir}")

    output = Path(output_path)
    if output.exists() and output.is_dir():
        output = output / f"{resolved}-bundle-{_now_iso().replace(':', '-')}.zip"
    elif output.suffix.lower() != ".zip":
        output = output.with_suffix(".zip")

    output.parent.mkdir(parents=True, exist_ok=True)

    artifact_paths = get_artifact_paths(resolved)
    included_files = [
        get_state_file(resolved),
        get_project_meta_file(resolved),
        project_dir / "USER_PROFILE.md",
        *artifact_paths.values(),
    ]

    manifest = {
        "bundle_schema_version": 1,
        "project_id": resolved,
        "exported_at": _now_iso(),
        "files": [],
    }

    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file_path in included_files:
            if not file_path.exists() or not file_path.is_file():
                continue
            rel = file_path.relative_to(project_dir).as_posix()
            arcname = f"project/{rel}"
            archive.write(file_path, arcname=arcname)
            manifest["files"].append(arcname)
        archive.writestr(
            "manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2)
        )

    from .state_logs import write_audit_log

    write_audit_log(
        event="PROJECT_EXPORT",
        detail=f"output={output} files={len(manifest['files'])}",
        project_id=resolved,
    )
    return output.resolve()


def import_project_bundle(
    bundle_path: Union[str, Path],
    project_id: Optional[str] = None,
    *,
    set_active: bool = True,
    overwrite: bool = False,
) -> str:
    """Import state/artifacts bundle into a target project."""
    bundle = Path(bundle_path)
    if not bundle.exists() or not bundle.is_file():
        raise FileNotFoundError(f"Bundle not found: {bundle}")

    target_project = resolve_project_id(project_id)
    target_dir = get_project_dir(target_project)

    if (
        not overwrite
        and target_dir.exists()
        and any(entry.name != PROJECT_META_FILE_NAME for entry in target_dir.iterdir())
    ):
        raise RuntimeError(
            f"Target project '{target_project}' already has files. Use overwrite=True."
        )

    if overwrite:
        shutil.rmtree(target_dir, ignore_errors=True)

    create_project(target_project, set_active=False)
    target_dir = get_project_dir(target_project)

    with zipfile.ZipFile(bundle, "r") as archive:
        members = [name for name in archive.namelist() if name.startswith("project/")]
        for member in members:
            rel = Path(member).relative_to("project")
            if rel.is_absolute() or ".." in rel.parts:
                continue
            destination = target_dir / rel
            destination.parent.mkdir(parents=True, exist_ok=True)
            if member.endswith("/"):
                destination.mkdir(parents=True, exist_ok=True)
                continue
            with archive.open(member) as src, open(destination, "wb") as dst:
                shutil.copyfileobj(src, dst)

    init_workspace(project_id=target_project)
    touch_project(target_project, mark_active=set_active)

    if set_active:
        from ludens_flow.core.paths import set_active_project_id

        set_active_project_id(target_project)

    from .state_logs import write_audit_log

    write_audit_log(
        event="PROJECT_IMPORT",
        detail=f"bundle={bundle.resolve()} overwrite={overwrite}",
        project_id=target_project,
    )
    return target_project
