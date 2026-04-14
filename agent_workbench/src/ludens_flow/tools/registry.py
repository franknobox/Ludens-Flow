from typing import Any, Dict, List, Optional

from ludens_flow.tools.search import SEARCH_TOOL_SCHEMA, web_search
from ludens_flow.tools.unity_files import (
    UNITY_FIND_FILES_TOOL_SCHEMA,
    UNITY_LIST_DIR_TOOL_SCHEMA,
    UNITY_READ_FILE_TOOL_SCHEMA,
    unity_find_files,
    unity_list_dir,
    unity_read_file,
)


COMMON_TOOL_SCHEMAS: List[Dict[str, Any]] = [
    SEARCH_TOOL_SCHEMA,
    UNITY_LIST_DIR_TOOL_SCHEMA,
    UNITY_READ_FILE_TOOL_SCHEMA,
    UNITY_FIND_FILES_TOOL_SCHEMA,
]


def merge_tool_schemas(
    extra_tools: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    merged: List[Dict[str, Any]] = []
    seen_names = set()

    for tool in COMMON_TOOL_SCHEMAS + list(extra_tools or []):
        fn = (tool or {}).get("function", {})
        name = fn.get("name")
        if not name or name in seen_names:
            continue
        seen_names.add(name)
        merged.append(tool)
    return merged


def dispatch_tool_call(
    tool_name: str, args: Dict[str, Any], project_id: Optional[str] = None
) -> str:
    if tool_name == "web_search":
        return web_search(args.get("query", ""))

    if tool_name == "unity_list_dir":
        return unity_list_dir(
            relative_path=args.get("relative_path", ""),
            max_entries=args.get("max_entries", 200),
            project_id=project_id,
        )

    if tool_name == "unity_read_file":
        return unity_read_file(
            relative_path=args.get("relative_path", ""),
            max_chars=args.get("max_chars", 12000),
            project_id=project_id,
        )

    if tool_name == "unity_find_files":
        return unity_find_files(
            pattern=args.get("pattern", "*.cs"),
            relative_path=args.get("relative_path", ""),
            max_results=args.get("max_results", 200),
            project_id=project_id,
        )

    return f"Error: Tool '{tool_name}' not found."
