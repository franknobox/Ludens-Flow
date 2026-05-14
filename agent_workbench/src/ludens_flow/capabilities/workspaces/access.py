"""
文件功能：工作区访问模块（access.py），统一管理路径边界与访问策略。
核心内容：提供工作区绑定解析、沙箱校验和读写权限判断能力。
核心内容：为工具层提供稳定工作区访问契约，减少业务分支复杂度。
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Literal, Optional

from ludens_flow.core.paths import (
    get_project_agent_file_write_enabled,
    get_project_workspace,
    list_project_workspaces,
    resolve_project_id,
)

WorkspaceOperation = Literal["read", "write", "create"]

DEFAULT_TEXT_FILE_EXTENSIONS = frozenset(
    {
        ".asmdef",
        ".cs",
        ".hlsl",
        ".json",
        ".md",
        ".shader",
        ".txt",
        ".uss",
        ".uxml",
        ".yaml",
        ".yml",
    }
)

_WINDOWS_DRIVE_RE = re.compile(r"^[A-Za-z]:[\\/]")
_ENV_EXPANSION_RE = re.compile(r"^(~|%[^%]+%|\$[A-Za-z_][A-Za-z0-9_]*|\$\{.+\})")
_GLOB_PATTERN_RE = re.compile(r"[*?\[\]{}]")


class WorkspaceAccessError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message

    def __str__(self) -> str:
        return f"[WORKSPACE_ACCESS_ERROR:{self.code}] {self.message}"


@dataclass(frozen=True)
class WorkspaceBinding:
    project_id: str
    workspace: dict
    root: Path


@dataclass(frozen=True)
class WorkspaceTarget:
    binding: WorkspaceBinding
    relative_path: str
    target: Path
    operation: WorkspaceOperation


def _clean_input_path(relative_path: str, *, allow_empty: bool, allow_glob: bool) -> str:
    raw = str(relative_path or "").strip()
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in {'"', "'"}:
        raw = raw[1:-1].strip()

    if not raw:
        if allow_empty:
            return ""
        raise WorkspaceAccessError("EMPTY_PATH", "A relative path is required.")

    if _ENV_EXPANSION_RE.match(raw):
        raise WorkspaceAccessError(
            "EXPANSION_NOT_ALLOWED",
            "Home, environment, or shell-expanded paths are not allowed. Use a relative path inside the approved workspace.",
        )

    if raw.startswith("\\\\"):
        raise WorkspaceAccessError(
            "UNC_PATH_NOT_ALLOWED",
            "UNC paths are not allowed. Use a relative path inside the approved workspace.",
        )

    if _WINDOWS_DRIVE_RE.match(raw) or Path(raw).is_absolute():
        raise WorkspaceAccessError(
            "ABSOLUTE_PATH_NOT_ALLOWED",
            "Only relative paths inside the approved workspace are allowed.",
        )

    normalized = raw.replace("\\", "/")
    if not allow_glob and _GLOB_PATTERN_RE.search(normalized):
        raise WorkspaceAccessError(
            "GLOB_NOT_ALLOWED",
            "Glob patterns are not allowed for this operation. Use explicit relative file paths.",
        )

    return normalized


def resolve_workspace_binding(
    project_id: Optional[str] = None,
    *,
    workspace_id: Optional[str] = None,
    kind: Optional[str] = None,
    require_enabled: bool = True,
    require_writable: bool = False,
) -> WorkspaceBinding:
    resolved_project_id = resolve_project_id(project_id)
    if not resolved_project_id:
        raise WorkspaceAccessError("PROJECT_NOT_RESOLVED", "Project id could not be resolved.")

    workspace = None
    if workspace_id or kind:
        workspace = get_project_workspace(
            resolved_project_id,
            workspace_id=workspace_id,
            kind=kind,
            require_enabled=require_enabled,
        )
    else:
        candidates = list_project_workspaces(
            resolved_project_id,
            kind=kind,
            include_disabled=not require_enabled,
        )
        if require_enabled:
            candidates = [item for item in candidates if item.get("enabled", True)]
        if not candidates:
            raise WorkspaceAccessError(
                "WORKSPACE_NOT_CONFIGURED",
                "No approved workspace is configured for the current project.",
            )
        if len(candidates) > 1:
            raise WorkspaceAccessError(
                "WORKSPACE_AMBIGUOUS",
                "Multiple approved workspaces are available. Specify a workspace_id explicitly.",
            )
        workspace = candidates[0]

    if not workspace:
        raise WorkspaceAccessError(
            "WORKSPACE_NOT_FOUND",
            "The requested workspace could not be found in the project workspace list.",
        )

    if require_enabled and not workspace.get("enabled", True):
        raise WorkspaceAccessError(
            "WORKSPACE_DISABLED",
            f"Workspace '{workspace.get('id', '')}' is currently disabled.",
        )

    if require_writable and not workspace.get("writable", False):
        raise WorkspaceAccessError(
            "WORKSPACE_NOT_WRITABLE",
            f"Workspace '{workspace.get('id', '')}' is not writable.",
        )

    root = Path(str(workspace.get("root", "") or "")).resolve()
    if not root.exists() or not root.is_dir():
        raise WorkspaceAccessError(
            "WORKSPACE_UNAVAILABLE",
            f"Approved workspace is unavailable: {root}",
        )

    return WorkspaceBinding(
        project_id=resolved_project_id,
        workspace=dict(workspace),
        root=root,
    )


def resolve_workspace_target(
    project_id: Optional[str] = None,
    *,
    workspace_id: Optional[str] = None,
    kind: Optional[str] = None,
    relative_path: str,
    operation: WorkspaceOperation,
    require_enabled: bool = True,
    require_writable: bool = False,
    allow_empty: bool = False,
    allow_glob: bool = False,
) -> WorkspaceTarget:
    binding = resolve_workspace_binding(
        project_id,
        workspace_id=workspace_id,
        kind=kind,
        require_enabled=require_enabled,
        require_writable=require_writable,
    )
    normalized_relative_path = _clean_input_path(
        relative_path,
        allow_empty=allow_empty,
        allow_glob=allow_glob,
    )
    target = (
        binding.root
        if not normalized_relative_path
        else (binding.root / normalized_relative_path).resolve()
    )
    try:
        target.relative_to(binding.root)
    except ValueError as exc:
        raise WorkspaceAccessError(
            "PATH_ESCAPE",
            "Path escapes the approved workspace root.",
        ) from exc

    return WorkspaceTarget(
        binding=binding,
        relative_path=normalized_relative_path,
        target=target,
        operation=operation,
    )


def ensure_text_file_target(
    workspace_target: WorkspaceTarget | str,
    *,
    allowed_extensions: Optional[Iterable[str]] = None,
) -> str:
    relative_path = (
        workspace_target.relative_path
        if isinstance(workspace_target, WorkspaceTarget)
        else str(workspace_target or "")
    )
    suffix = Path(relative_path).suffix.lower()
    allowed = {
        str(item).strip().lower()
        for item in (allowed_extensions or DEFAULT_TEXT_FILE_EXTENSIONS)
        if str(item).strip()
    }
    if suffix not in allowed:
        raise WorkspaceAccessError(
            "FILE_TYPE_NOT_ALLOWED",
            f"File type '{suffix or '(no extension)'}' is not allowed for this workspace operation.",
        )
    return suffix


def check_workspace_write_permission(
    project_id: Optional[str],
    *,
    workspace_id: Optional[str],
    relative_path: str,
    file_kind: str = "text",
    allowed_extensions: Optional[Iterable[str]] = None,
) -> WorkspaceTarget:
    operation: WorkspaceOperation
    binding = resolve_workspace_binding(
        project_id,
        workspace_id=workspace_id,
        require_enabled=True,
        require_writable=True,
    )
    if not get_project_agent_file_write_enabled(binding.project_id):
        raise WorkspaceAccessError(
            "PROJECT_WRITE_DISABLED",
            "Agent file writing is disabled for the current project.",
        )
    target_path = (binding.root / _clean_input_path(relative_path, allow_empty=False, allow_glob=False)).resolve()
    try:
        target_path.relative_to(binding.root)
    except ValueError as exc:
        raise WorkspaceAccessError(
            "PATH_ESCAPE",
            "Path escapes the approved workspace root.",
        ) from exc

    operation = "write" if target_path.exists() else "create"
    workspace_target = WorkspaceTarget(
        binding=binding,
        relative_path=_clean_input_path(relative_path, allow_empty=False, allow_glob=False),
        target=target_path,
        operation=operation,
    )
    if file_kind == "text":
        ensure_text_file_target(workspace_target, allowed_extensions=allowed_extensions)
    return workspace_target


# ---------------------------------------------------------------------------
# 工作区上下文摘要（供 Agent 注入上下文使用）
# ---------------------------------------------------------------------------

_SKIP_DIRS = frozenset({
    "__pycache__", ".git", ".svn", ".hg", "node_modules",
    ".vs", ".idea", ".vscode", "Temp", "Library", "obj", "bin",
    "Logs", "UserSettings",
})

_CONTEXT_EXTENSIONS = frozenset({
    ".cs", ".py", ".js", ".ts", ".json", ".yaml", ".yml",
    ".md", ".txt", ".shader", ".hlsl", ".uxml", ".uss",
    ".asmdef", ".tscn", ".gd", ".cfg",
})


def _walk_tree(
    root: Path,
    rel: str,
    lines: List[str],
    *,
    max_files: int,
    file_count: List[int],
    depth: int,
    max_depth: int,
) -> None:
    if depth > max_depth or file_count[0] >= max_files:
        return
    indent = "  " * depth
    try:
        entries = sorted(root.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
    except PermissionError:
        return
    dirs = [e for e in entries if e.is_dir() and e.name not in _SKIP_DIRS]
    files = [e for e in entries if e.is_file() and e.suffix.lower() in _CONTEXT_EXTENSIONS]
    for d in dirs:
        lines.append(f"{indent}{d.name}/")
        _walk_tree(
            d,
            f"{rel}/{d.name}" if rel else d.name,
            lines,
            max_files=max_files,
            file_count=file_count,
            depth=depth + 1,
            max_depth=max_depth,
        )
        if file_count[0] >= max_files:
            break
    for f in files:
        if file_count[0] >= max_files:
            lines.append(f"{indent}... (文件过多，已截断)")
            break
        lines.append(f"{indent}{f.name}")
        file_count[0] += 1


def build_workspace_context_for_prompt(
    project_id: Optional[str] = None,
    *,
    max_files: int = 120,
    max_depth: int = 5,
) -> str:
    """生成工作区文件树摘要文本，供 Agent 系统提示注入使用。

    只列出代码/配置/文档类文件，跳过构建产物、版本控制目录等。
    结果紧凑、有界，不读取任何文件内容。
    """
    resolved = resolve_project_id(project_id)
    if not resolved:
        return ""

    workspaces = list_project_workspaces(resolved)
    if not workspaces:
        return ""

    enabled = [ws for ws in workspaces if ws.get("enabled", True)]
    if not enabled:
        return ""

    sections: List[str] = []
    for ws in enabled:
        root = Path(str(ws.get("root", "") or "")).resolve()
        if not root.exists() or not root.is_dir():
            continue
        ws_id = ws.get("id") or ws.get("workspace_id") or root.name
        ws_label = ws.get("label") or ws_id
        lines: List[str] = []
        file_count: List[int] = [0]
        _walk_tree(root, "", lines, max_files=max_files, file_count=file_count, depth=0, max_depth=max_depth)
        if lines:
            tree_text = "\n".join(lines)
            sections.append(
                f"工作区：{ws_label}（{ws_id}）根目录：{root}\n"
                f"{tree_text}\n"
                f"共 {file_count[0]} 个可读文件"
            )

    if not sections:
        return ""

    body = "\n\n".join(sections)
    return (
        "[WORKSPACE_FILES]\n"
        "以下是当前项目工作区的文件结构（仅列出代码/配置/文档类文件）：\n\n"
        f"{body}\n"
        "[/WORKSPACE_FILES]"
    )
