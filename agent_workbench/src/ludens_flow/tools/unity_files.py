import fnmatch
from pathlib import Path
from typing import Optional

from ludens_flow.paths import get_project_unity_root, resolve_project_id


def _bound_unity_root(project_id: Optional[str] = None) -> Path:
    resolved = resolve_project_id(project_id)
    unity_root = get_project_unity_root(resolved)
    if not unity_root:
        raise RuntimeError(
            "Unity project is not bound for current project. Use '/unity bind <path>' first."
        )

    root = Path(unity_root).resolve()
    if not root.exists() or not root.is_dir():
        raise RuntimeError(f"Bound Unity path is unavailable: {root}")
    return root


def _resolve_inside_root(root: Path, relative_path: str = "") -> Path:
    rel = str(relative_path or "").strip()
    target = (root / rel).resolve() if rel else root
    try:
        target.relative_to(root)
    except ValueError:
        raise RuntimeError("Path escapes bound Unity project root.")
    return target


def unity_list_dir(
    relative_path: str = "",
    max_entries: int = 200,
    project_id: Optional[str] = None,
) -> str:
    root = _bound_unity_root(project_id)
    target = _resolve_inside_root(root, relative_path)

    if not target.exists() or not target.is_dir():
        raise RuntimeError(f"Directory does not exist: {target}")

    entries = sorted(
        target.iterdir(),
        key=lambda item: (not item.is_dir(), item.name.lower()),
    )

    bounded_max = max(1, min(int(max_entries or 200), 1000))
    shown = entries[:bounded_max]

    lines = [f"Unity Root: {root}", f"Directory: {target}"]
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
) -> str:
    root = _bound_unity_root(project_id)
    target = _resolve_inside_root(root, relative_path)

    if not target.exists() or not target.is_file():
        raise RuntimeError(f"File does not exist: {target}")

    bounded_max = max(200, min(int(max_chars or 12000), 200000))
    content = target.read_text(encoding="utf-8", errors="replace")
    truncated = content[:bounded_max]

    if len(content) > bounded_max:
        truncated += (
            f"\n\n... truncated at {bounded_max} chars (total {len(content)} chars)"
        )

    return f"Unity Root: {root}\nFile: {target}\n\n{truncated}"


def unity_find_files(
    pattern: str = "*.cs",
    relative_path: str = "",
    max_results: int = 200,
    project_id: Optional[str] = None,
) -> str:
    root = _bound_unity_root(project_id)
    start = _resolve_inside_root(root, relative_path)

    if not start.exists() or not start.is_dir():
        raise RuntimeError(f"Search directory does not exist: {start}")

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
            },
        },
    },
}
