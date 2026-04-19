import fnmatch
from pathlib import Path
from typing import Optional

from ludens_flow.capabilities.workspaces import (
    WorkspaceAccessError,
    resolve_workspace_binding,
    resolve_workspace_target,
)


class UnityToolError(WorkspaceAccessError):
    def __init__(self, code: str, message: str):
        super().__init__(code, message)
        self.code = code
        self.message = message

    def __str__(self) -> str:
        return f"[UNITY_TOOL_ERROR:{self.code}] {self.message}"


def _bound_unity_workspace(
    project_id: Optional[str] = None, workspace_id: Optional[str] = None
) -> tuple[str, dict, Path]:
    try:
        binding = resolve_workspace_binding(
            project_id,
            workspace_id=workspace_id,
            kind="unity",
            require_enabled=True,
        )
    except WorkspaceAccessError as exc:
        raise UnityToolError(
            exc.code,
            exc.message,
        )
    return binding.project_id, binding.workspace, binding.root


def unity_list_dir(
    relative_path: str = "",
    max_entries: int = 200,
    project_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
) -> str:
    resolved_project_id, workspace, root = _bound_unity_workspace(project_id, workspace_id)
    try:
        target = resolve_workspace_target(
            resolved_project_id,
            workspace_id=workspace.get("id"),
            kind="unity",
            relative_path=relative_path,
            operation="read",
            allow_empty=True,
        ).target
    except WorkspaceAccessError as exc:
        raise UnityToolError(exc.code, exc.message) from exc

    if not target.exists() or not target.is_dir():
        raise UnityToolError("DIRECTORY_NOT_FOUND", f"Directory does not exist: {target}")

    entries = sorted(
        target.iterdir(),
        key=lambda item: (not item.is_dir(), item.name.lower()),
    )

    bounded_max = max(1, min(int(max_entries or 200), 1000))
    shown = entries[:bounded_max]

    lines = [
        f"Workspace: {workspace.get('id', '')} ({workspace.get('label', '')})",
        f"Unity Root: {root}",
        f"Directory: {target}",
    ]
    for item in shown:
        label = item.name + ("/" if item.is_dir() else "")
        lines.append(f"- {label}")

    if len(entries) > bounded_max:
        lines.append(f"... truncated: showing {bounded_max}/{len(entries)} entries")

    if len(lines) == 2:
        lines.append("(empty)")

    return "\n".join(lines)


def unity_read_file(
    relative_path: str,
    max_chars: int = 12000,
    project_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
) -> str:
    resolved_project_id, workspace, root = _bound_unity_workspace(project_id, workspace_id)
    try:
        target = resolve_workspace_target(
            resolved_project_id,
            workspace_id=workspace.get("id"),
            kind="unity",
            relative_path=relative_path,
            operation="read",
        ).target
    except WorkspaceAccessError as exc:
        raise UnityToolError(exc.code, exc.message) from exc

    if not target.exists() or not target.is_file():
        raise UnityToolError("FILE_NOT_FOUND", f"File does not exist: {target}")

    bounded_max = max(200, min(int(max_chars or 12000), 200000))
    content = target.read_text(encoding="utf-8", errors="replace")
    truncated = content[:bounded_max]

    if len(content) > bounded_max:
        truncated += (
            f"\n\n... truncated at {bounded_max} chars (total {len(content)} chars)"
        )

    return (
        f"Workspace: {workspace.get('id', '')} ({workspace.get('label', '')})\n"
        f"Unity Root: {root}\nFile: {target}\n\n{truncated}"
    )


def unity_find_files(
    pattern: str = "*.cs",
    relative_path: str = "",
    max_results: int = 200,
    project_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
) -> str:
    resolved_project_id, workspace, root = _bound_unity_workspace(project_id, workspace_id)
    try:
        start = resolve_workspace_target(
            resolved_project_id,
            workspace_id=workspace.get("id"),
            kind="unity",
            relative_path=relative_path,
            operation="read",
            allow_empty=True,
        ).target
    except WorkspaceAccessError as exc:
        raise UnityToolError(exc.code, exc.message) from exc

    if not start.exists() or not start.is_dir():
        raise UnityToolError(
            "SEARCH_DIRECTORY_NOT_FOUND", f"Search directory does not exist: {start}"
        )

    bounded_max = max(1, min(int(max_results or 200), 2000))
    normalized_pattern = str(pattern or "*.cs").strip() or "*.cs"

    matches = []
    for file_path in start.rglob("*"):
        if not file_path.is_file():
            continue
        rel = file_path.relative_to(root).as_posix()
        if fnmatch.fnmatch(rel, normalized_pattern) or fnmatch.fnmatch(
            file_path.name, normalized_pattern
        ):
            matches.append(rel)
            if len(matches) >= bounded_max:
                break

    lines = [
        f"Workspace: {workspace.get('id', '')} ({workspace.get('label', '')})",
        f"Unity Root: {root}",
        f"Search Start: {start}",
        f"Pattern: {normalized_pattern}",
    ]
    if not matches:
        lines.append("(no matches)")
        return "\n".join(lines)

    lines.extend(f"- {item}" for item in matches)
    if len(matches) >= bounded_max:
        lines.append(f"... truncated at {bounded_max} results")
    return "\n".join(lines)


UNITY_LIST_DIR_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "unity_list_dir",
        "description": "List files and folders under the bound Unity project root in read-only mode.",
        "parameters": {
            "type": "object",
            "properties": {
                "relative_path": {
                    "type": "string",
                    "description": "Relative path inside the Unity project root. Empty means root.",
                },
                "max_entries": {
                    "type": "integer",
                    "description": "Maximum number of entries to show (1-1000).",
                },
                "workspace_id": {
                    "type": "string",
                    "description": "Optional Unity workspace id from the project's approved workspace list.",
                },
            },
        },
    },
}


UNITY_READ_FILE_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "unity_read_file",
        "description": "Read a text file from the bound Unity project root in read-only mode.",
        "parameters": {
            "type": "object",
            "properties": {
                "relative_path": {
                    "type": "string",
                    "description": "Required relative file path inside the Unity project root.",
                },
                "max_chars": {
                    "type": "integer",
                    "description": "Maximum characters to return (200-200000).",
                },
                "workspace_id": {
                    "type": "string",
                    "description": "Optional Unity workspace id from the project's approved workspace list.",
                },
            },
            "required": ["relative_path"],
        },
    },
}


UNITY_FIND_FILES_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "unity_find_files",
        "description": "Find files under bound Unity project root by glob-like pattern in read-only mode.",
        "parameters": {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Glob-like pattern, such as *.cs or Assets/**/*.prefab.",
                },
                "relative_path": {
                    "type": "string",
                    "description": "Relative directory where search starts. Empty means root.",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results to return (1-2000).",
                },
                "workspace_id": {
                    "type": "string",
                    "description": "Optional Unity workspace id from the project's approved workspace list.",
                },
            },
        },
    },
}
