"""
文件功能：能力工具模块（workspace_files.py），对外提供可控工具调用能力。
核心内容：封装工具参数处理、错误返回与结果摘要的统一行为。
核心内容：作为 Agent 工具层能力入口，服务文件/搜索/工作区相关任务。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Iterable, Optional

from ludens_flow.capabilities.workspaces import (
    WorkspaceAccessError,
    check_workspace_write_permission,
    ensure_text_file_target,
    resolve_workspace_binding,
    resolve_workspace_target,
)

_ToolEventHandler = Optional[Callable[[dict[str, Any]], None]]
_WRITE_TOOL_NAMES = {
    "workspace_create_directory",
    "workspace_write_text_file",
    "workspace_patch_text_file",
    "workspace_delete_file",
}


def _emit_tool_event(event_handler: _ToolEventHandler, payload: dict[str, Any]) -> Any:
    if event_handler:
        return event_handler(payload)
    return None


def _emit_permission_event(
    event_handler: _ToolEventHandler,
    *,
    event_type: str,
    tool_name: str,
    workspace_id: Optional[str],
    path: str,
    message: str,
) -> Any:
    return _emit_tool_event(
        event_handler,
        {
            "type": event_type,
            "tool_name": tool_name,
            "args": {
                "workspace_id": workspace_id,
                "path": path,
            },
            "message": message,
        },
    )


def _resolve_write_target_with_events(
    *,
    tool_name: str,
    path: str,
    workspace_id: Optional[str],
    project_id: Optional[str],
    tool_event_handler: _ToolEventHandler,
    file_kind: str = "text",
):
    if tool_name in _WRITE_TOOL_NAMES:
        approved = _emit_permission_event(
            tool_event_handler,
            event_type="permission_required",
            tool_name=tool_name,
            workspace_id=workspace_id,
            path=path,
            message=f"Checking write permission for: {path}",
        )
        if approved is False:
            _emit_permission_event(
                tool_event_handler,
                event_type="permission_denied",
                tool_name=tool_name,
                workspace_id=workspace_id,
                path=path,
                message=f"User denied write permission for: {path}",
            )
            raise WorkspaceAccessError(
                "PERMISSION_DENIED",
                "User denied this workspace write operation.",
            )
    try:
        target = check_workspace_write_permission(
            project_id,
            workspace_id=workspace_id,
            relative_path=path,
            file_kind=file_kind,
        )
    except WorkspaceAccessError as exc:
        if tool_name in _WRITE_TOOL_NAMES:
            _emit_permission_event(
                tool_event_handler,
                event_type="permission_denied",
                tool_name=tool_name,
                workspace_id=workspace_id,
                path=path,
                message=str(exc),
            )
        raise

    if tool_name in _WRITE_TOOL_NAMES:
        _emit_permission_event(
            tool_event_handler,
            event_type="permission_granted",
            tool_name=tool_name,
            workspace_id=target.binding.workspace.get("id"),
            path=target.relative_path,
            message=f"Write permission granted for: {target.relative_path}",
        )
    return target


def _read_text_file(path: Path, *, max_chars: int) -> tuple[str, bool]:
    content = path.read_text(encoding="utf-8", errors="replace")
    if len(content) <= max_chars:
        return content, False
    return content[:max_chars], True


def _normalize_text(value: Any) -> str:
    return str(value or "")


def workspace_read_files_batch(
    paths: list[str],
    *,
    workspace_id: Optional[str] = None,
    project_id: Optional[str] = None,
    max_chars_per_file: int = 12000,
    max_total_chars: int = 40000,
) -> str:
    if not isinstance(paths, list) or not paths:
        raise WorkspaceAccessError(
            "INVALID_ARGUMENT", "Provide a non-empty list of relative file paths."
        )

    bounded_max_per_file = max(200, min(int(max_chars_per_file or 12000), 100000))
    bounded_max_total = max(
        bounded_max_per_file, min(int(max_total_chars or 40000), 300000)
    )

    binding = resolve_workspace_binding(project_id, workspace_id=workspace_id)
    unique_paths: list[str] = []
    seen_paths: set[str] = set()
    for raw_path in paths[:20]:
        resolved = resolve_workspace_target(
            binding.project_id,
            workspace_id=binding.workspace.get("id"),
            relative_path=raw_path,
            operation="read",
        )
        ensure_text_file_target(resolved)
        if not resolved.target.exists() or not resolved.target.is_file():
            raise WorkspaceAccessError(
                "FILE_NOT_FOUND",
                f"File does not exist in workspace: {resolved.relative_path}",
            )
        if resolved.relative_path in seen_paths:
            continue
        seen_paths.add(resolved.relative_path)
        unique_paths.append(resolved.relative_path)

    total_chars = 0
    blocks: list[str] = []
    truncated_files: list[str] = []
    total_truncated = False

    for relative_path in unique_paths:
        target = resolve_workspace_target(
            binding.project_id,
            workspace_id=binding.workspace.get("id"),
            relative_path=relative_path,
            operation="read",
        )
        remaining = bounded_max_total - total_chars
        if remaining <= 0:
            total_truncated = True
            break
        content, per_file_truncated = _read_text_file(
            target.target, max_chars=min(bounded_max_per_file, remaining)
        )
        total_chars += len(content)
        if per_file_truncated:
            truncated_files.append(relative_path)
        blocks.append(
            f"--- [Attached Workspace File] {relative_path} ---\n{content}"
        )

    summary_lines = [
        f"Workspace: {binding.workspace.get('id', '')} ({binding.workspace.get('label', '')})",
        f"Workspace Root: {binding.root}",
        f"Files Read: {len(blocks)}",
    ]
    if truncated_files:
        summary_lines.append(
            "Per-file truncation: " + ", ".join(truncated_files)
        )
    if total_truncated:
        summary_lines.append(
            f"Total output truncated at {bounded_max_total} chars."
        )

    return "\n".join(summary_lines) + "\n\n" + "\n\n".join(blocks)


def workspace_write_text_file(
    path: str,
    content: str,
    *,
    workspace_id: Optional[str] = None,
    project_id: Optional[str] = None,
    tool_event_handler: _ToolEventHandler = None,
) -> str:
    target = _resolve_write_target_with_events(
        tool_name="workspace_write_text_file",
        path=path,
        workspace_id=workspace_id,
        project_id=project_id,
        tool_event_handler=tool_event_handler,
    )
    if target.target.exists() and not target.target.is_file():
        raise WorkspaceAccessError(
            "TARGET_NOT_A_FILE",
            f"Target exists but is not a file: {target.relative_path}",
        )
    _emit_tool_event(
        tool_event_handler,
        {
            "type": "tool_progress",
            "tool_name": "workspace_write_text_file",
            "args": {
                "workspace_id": target.binding.workspace.get("id"),
                "path": target.relative_path,
            },
            "message": f"Writing file: {target.relative_path}",
        },
    )

    previous_content = (
        target.target.read_text(encoding="utf-8", errors="replace")
        if target.target.exists()
        else None
    )
    target.target.write_text(_normalize_text(content), encoding="utf-8")

    change_type = "created" if previous_content is None else "modified"
    _emit_tool_event(
        tool_event_handler,
        {
            "type": "file_changed",
            "tool_name": "workspace_write_text_file",
            "args": {
                "workspace_id": target.binding.workspace.get("id"),
                "path": target.relative_path,
            },
            "workspace_id": target.binding.workspace.get("id"),
            "workspace_label": target.binding.workspace.get("label", ""),
            "path": target.relative_path,
            "change_type": change_type,
            "summary": (
                f"{change_type.capitalize()} {target.relative_path} "
                f"({len(_normalize_text(content))} chars)"
            ),
        },
    )

    return (
        f"Workspace: {target.binding.workspace.get('id', '')} ({target.binding.workspace.get('label', '')})\n"
        f"File: {target.relative_path}\n"
        f"Result: {change_type}\n"
        f"Characters Written: {len(_normalize_text(content))}"
    )


def workspace_create_directory(
    path: str,
    *,
    workspace_id: Optional[str] = None,
    project_id: Optional[str] = None,
    tool_event_handler: _ToolEventHandler = None,
) -> str:
    target = _resolve_write_target_with_events(
        tool_name="workspace_create_directory",
        path=path,
        workspace_id=workspace_id,
        project_id=project_id,
        tool_event_handler=tool_event_handler,
        file_kind="directory",
    )
    if target.target.exists() and not target.target.is_dir():
        raise WorkspaceAccessError(
            "TARGET_NOT_A_DIRECTORY",
            f"Target exists but is not a directory: {target.relative_path}",
        )

    _emit_tool_event(
        tool_event_handler,
        {
            "type": "tool_progress",
            "tool_name": "workspace_create_directory",
            "args": {
                "workspace_id": target.binding.workspace.get("id"),
                "path": target.relative_path,
            },
            "message": f"Creating directory: {target.relative_path}",
        },
    )

    existed = target.target.exists()
    target.target.mkdir(parents=True, exist_ok=True)

    _emit_tool_event(
        tool_event_handler,
        {
            "type": "file_changed",
            "tool_name": "workspace_create_directory",
            "args": {
                "workspace_id": target.binding.workspace.get("id"),
                "path": target.relative_path,
            },
            "workspace_id": target.binding.workspace.get("id"),
            "workspace_label": target.binding.workspace.get("label", ""),
            "path": target.relative_path,
            "change_type": "directory_created" if not existed else "directory_verified",
            "summary": (
                f"{'Created' if not existed else 'Verified'} directory {target.relative_path}"
            ),
        },
    )

    return (
        f"Workspace: {target.binding.workspace.get('id', '')} ({target.binding.workspace.get('label', '')})\n"
        f"Directory: {target.relative_path}\n"
        f"Result: {'created' if not existed else 'already_exists'}"
    )


def workspace_delete_file(
    path: str,
    *,
    workspace_id: Optional[str] = None,
    project_id: Optional[str] = None,
    tool_event_handler: _ToolEventHandler = None,
) -> str:
    target = _resolve_write_target_with_events(
        tool_name="workspace_delete_file",
        path=path,
        workspace_id=workspace_id,
        project_id=project_id,
        tool_event_handler=tool_event_handler,
    )
    if not target.target.exists():
        raise WorkspaceAccessError(
            "FILE_NOT_FOUND",
            f"File does not exist in workspace: {target.relative_path}",
        )
    if not target.target.is_file():
        raise WorkspaceAccessError(
            "TARGET_NOT_A_FILE",
            f"Target is not a file: {target.relative_path}",
        )

    _emit_tool_event(
        tool_event_handler,
        {
            "type": "tool_progress",
            "tool_name": "workspace_delete_file",
            "args": {
                "workspace_id": target.binding.workspace.get("id"),
                "path": target.relative_path,
            },
            "message": f"Deleting file: {target.relative_path}",
        },
    )

    target.target.unlink()

    _emit_tool_event(
        tool_event_handler,
        {
            "type": "file_changed",
            "tool_name": "workspace_delete_file",
            "args": {
                "workspace_id": target.binding.workspace.get("id"),
                "path": target.relative_path,
            },
            "workspace_id": target.binding.workspace.get("id"),
            "workspace_label": target.binding.workspace.get("label", ""),
            "path": target.relative_path,
            "change_type": "deleted",
            "summary": f"Deleted file {target.relative_path}",
        },
    )

    return (
        f"Workspace: {target.binding.workspace.get('id', '')} ({target.binding.workspace.get('label', '')})\n"
        f"File: {target.relative_path}\n"
        "Result: deleted"
    )


def workspace_patch_text_file(
    path: str,
    patches: list[dict[str, Any]],
    *,
    workspace_id: Optional[str] = None,
    project_id: Optional[str] = None,
    tool_event_handler: _ToolEventHandler = None,
) -> str:
    if not isinstance(patches, list) or not patches:
        raise WorkspaceAccessError(
            "INVALID_ARGUMENT",
            "Provide a non-empty list of patch operations.",
        )

    target = _resolve_write_target_with_events(
        tool_name="workspace_patch_text_file",
        path=path,
        workspace_id=workspace_id,
        project_id=project_id,
        tool_event_handler=tool_event_handler,
    )
    if not target.target.exists():
        raise WorkspaceAccessError(
            "FILE_NOT_FOUND",
            f"File does not exist in workspace: {target.relative_path}",
        )
    if not target.target.is_file():
        raise WorkspaceAccessError(
            "TARGET_NOT_A_FILE",
            f"Target is not a file: {target.relative_path}",
        )

    original = target.target.read_text(encoding="utf-8", errors="replace")
    updated = original
    applied = 0

    _emit_tool_event(
        tool_event_handler,
        {
            "type": "tool_progress",
            "tool_name": "workspace_patch_text_file",
            "args": {
                "workspace_id": target.binding.workspace.get("id"),
                "path": target.relative_path,
            },
            "message": f"Patching file: {target.relative_path}",
        },
    )

    for index, patch in enumerate(patches, start=1):
        if not isinstance(patch, dict):
            raise WorkspaceAccessError(
                "INVALID_ARGUMENT",
                f"Patch #{index} must be an object.",
            )
        find = _normalize_text(patch.get("find"))
        replace = _normalize_text(patch.get("replace"))
        replace_all = bool(patch.get("replace_all", False))
        if not find:
            raise WorkspaceAccessError(
                "INVALID_ARGUMENT",
                f"Patch #{index} is missing a non-empty 'find' string.",
            )
        occurrences = updated.count(find)
        if occurrences <= 0:
            raise WorkspaceAccessError(
                "PATCH_TARGET_NOT_FOUND",
                f"Patch #{index} could not find target text in {target.relative_path}.",
            )
        if not replace_all and occurrences > 1:
            raise WorkspaceAccessError(
                "PATCH_AMBIGUOUS",
                f"Patch #{index} matched multiple locations in {target.relative_path}. Set replace_all=true to replace all occurrences.",
            )
        updated = (
            updated.replace(find, replace)
            if replace_all
            else updated.replace(find, replace, 1)
        )
        applied += occurrences if replace_all else 1

    if updated == original:
        raise WorkspaceAccessError(
            "PATCH_NO_CHANGE",
            f"Patches did not change the file: {target.relative_path}",
        )

    target.target.write_text(updated, encoding="utf-8")

    _emit_tool_event(
        tool_event_handler,
        {
            "type": "file_changed",
            "tool_name": "workspace_patch_text_file",
            "args": {
                "workspace_id": target.binding.workspace.get("id"),
                "path": target.relative_path,
            },
            "workspace_id": target.binding.workspace.get("id"),
            "workspace_label": target.binding.workspace.get("label", ""),
            "path": target.relative_path,
            "change_type": "patched",
            "summary": f"Patched {target.relative_path} ({applied} changes)",
        },
    )

    return (
        f"Workspace: {target.binding.workspace.get('id', '')} ({target.binding.workspace.get('label', '')})\n"
        f"File: {target.relative_path}\n"
        f"Result: patched\n"
        f"Changes Applied: {applied}"
    )


WORKSPACE_READ_FILES_BATCH_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "workspace_read_files_batch",
        "description": "Read multiple text files from an approved project workspace in a single call.",
        "parameters": {
            "type": "object",
            "properties": {
                "workspace_id": {
                    "type": "string",
                    "description": "Optional workspace id from the project's approved workspace list. Required when multiple workspaces are configured.",
                },
                "paths": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of relative file paths inside the approved workspace.",
                },
                "max_chars_per_file": {
                    "type": "integer",
                    "description": "Maximum characters per file (200-100000).",
                },
                "max_total_chars": {
                    "type": "integer",
                    "description": "Maximum total characters returned across all files (>= per-file cap, <= 300000).",
                },
            },
            "required": ["paths"],
        },
    },
}


WORKSPACE_WRITE_TEXT_FILE_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "workspace_write_text_file",
        "description": "Create or overwrite a text file inside an approved writable workspace. Only whitelisted text file types are allowed.",
        "parameters": {
            "type": "object",
            "properties": {
                "workspace_id": {
                    "type": "string",
                    "description": "Optional workspace id from the project's approved workspace list. Required when multiple workspaces are configured.",
                },
                "path": {
                    "type": "string",
                    "description": "Relative file path inside the approved writable workspace.",
                },
                "content": {
                    "type": "string",
                    "description": "UTF-8 text content to write.",
                },
            },
            "required": ["path", "content"],
        },
    },
}


WORKSPACE_CREATE_DIRECTORY_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "workspace_create_directory",
        "description": "Create a directory inside an approved writable workspace. Parent folders will be created when needed.",
        "parameters": {
            "type": "object",
            "properties": {
                "workspace_id": {
                    "type": "string",
                    "description": "Optional workspace id from the project's approved workspace list. Required when multiple workspaces are configured.",
                },
                "path": {
                    "type": "string",
                    "description": "Relative directory path inside the approved writable workspace.",
                },
            },
            "required": ["path"],
        },
    },
}


WORKSPACE_DELETE_FILE_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "workspace_delete_file",
        "description": "Delete a text file inside an approved writable workspace.",
        "parameters": {
            "type": "object",
            "properties": {
                "workspace_id": {
                    "type": "string",
                    "description": "Optional workspace id from the project's approved workspace list. Required when multiple workspaces are configured.",
                },
                "path": {
                    "type": "string",
                    "description": "Relative file path inside the approved writable workspace.",
                },
            },
            "required": ["path"],
        },
    },
}


WORKSPACE_PATCH_TEXT_FILE_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "workspace_patch_text_file",
        "description": "Apply exact text replacements to a text file inside an approved writable workspace.",
        "parameters": {
            "type": "object",
            "properties": {
                "workspace_id": {
                    "type": "string",
                    "description": "Optional workspace id from the project's approved workspace list. Required when multiple workspaces are configured.",
                },
                "path": {
                    "type": "string",
                    "description": "Relative file path inside the approved writable workspace.",
                },
                "patches": {
                    "type": "array",
                    "description": "One or more exact text replacement operations.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "find": {
                                "type": "string",
                                "description": "Exact text to find.",
                            },
                            "replace": {
                                "type": "string",
                                "description": "Replacement text.",
                            },
                            "replace_all": {
                                "type": "boolean",
                                "description": "When true, replace every occurrence instead of only one.",
                            },
                        },
                        "required": ["find", "replace"],
                    },
                },
            },
            "required": ["path", "patches"],
        },
    },
}
