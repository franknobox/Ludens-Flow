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


def _emit_tool_event(event_handler: _ToolEventHandler, payload: dict[str, Any]) -> None:
    if event_handler:
        event_handler(payload)


def _read_text_file(path: Path, *, max_chars: int) -> tuple[str, bool]:
    content = path.read_text(encoding="utf-8", errors="replace")
    if len(content) <= max_chars:
        return content, False
    return content[:max_chars], True


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
    target = check_workspace_write_permission(
        project_id,
        workspace_id=workspace_id,
        relative_path=path,
    )
    if target.target.exists() and not target.target.is_file():
        raise WorkspaceAccessError(
            "TARGET_NOT_A_FILE",
            f"Target exists but is not a file: {target.relative_path}",
        )
    if not target.target.parent.exists():
        raise WorkspaceAccessError(
            "PARENT_DIRECTORY_MISSING",
            f"Parent directory does not exist inside workspace: {target.target.parent}",
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
    target.target.write_text(str(content or ""), encoding="utf-8")

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
                f"({len(str(content or ''))} chars)"
            ),
        },
    )

    return (
        f"Workspace: {target.binding.workspace.get('id', '')} ({target.binding.workspace.get('label', '')})\n"
        f"File: {target.relative_path}\n"
        f"Result: {change_type}\n"
        f"Characters Written: {len(str(content or ''))}"
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
