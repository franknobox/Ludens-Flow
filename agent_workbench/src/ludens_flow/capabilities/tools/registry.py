"""
文件功能：能力工具模块（registry.py），对外提供可控工具调用能力。
核心内容：封装工具参数处理、错误返回与结果摘要的统一行为。
核心内容：作为 Agent 工具层能力入口，服务文件/搜索/工作区相关任务。
"""

from typing import Any, Callable, Dict, List, Optional

from ludens_flow.capabilities.mcp.adapter import (
    ENGINE_TOOL_SCHEMAS,
    dispatch_engine_tool_call,
)
from ludens_flow.capabilities.mcp.health import McpClientError
from ludens_flow.capabilities.tools.search import SEARCH_TOOL_SCHEMA, web_search
from ludens_flow.capabilities.tools.unity_files import (
    UNITY_FIND_FILES_TOOL_SCHEMA,
    UNITY_LIST_DIR_TOOL_SCHEMA,
    UNITY_READ_FILE_TOOL_SCHEMA,
    UnityToolError,
    unity_find_files,
    unity_list_dir,
    unity_read_file,
)
from ludens_flow.capabilities.tools.workspace_files import (
    WORKSPACE_CREATE_DIRECTORY_TOOL_SCHEMA,
    WORKSPACE_DELETE_FILE_TOOL_SCHEMA,
    WORKSPACE_PATCH_TEXT_FILE_TOOL_SCHEMA,
    WORKSPACE_READ_FILES_BATCH_TOOL_SCHEMA,
    WORKSPACE_WRITE_TEXT_FILE_TOOL_SCHEMA,
    workspace_create_directory,
    workspace_delete_file,
    workspace_patch_text_file,
    workspace_read_files_batch,
    workspace_write_text_file,
)
from ludens_flow.capabilities.workspaces import WorkspaceAccessError


COMMON_TOOL_SCHEMAS: List[Dict[str, Any]] = [
    SEARCH_TOOL_SCHEMA,
    WORKSPACE_CREATE_DIRECTORY_TOOL_SCHEMA,
    WORKSPACE_READ_FILES_BATCH_TOOL_SCHEMA,
    WORKSPACE_PATCH_TEXT_FILE_TOOL_SCHEMA,
    WORKSPACE_WRITE_TEXT_FILE_TOOL_SCHEMA,
    WORKSPACE_DELETE_FILE_TOOL_SCHEMA,
    UNITY_LIST_DIR_TOOL_SCHEMA,
    UNITY_READ_FILE_TOOL_SCHEMA,
    UNITY_FIND_FILES_TOOL_SCHEMA,
    *ENGINE_TOOL_SCHEMAS,
]


def list_common_tools() -> List[Dict[str, Any]]:
    catalog: List[Dict[str, Any]] = []
    for tool in COMMON_TOOL_SCHEMAS:
        fn = (tool or {}).get("function", {})
        name = str(fn.get("name", "") or "").strip()
        if not name:
            continue

        category = "general"
        workspace_kind = None
        requires_workspace = False
        writes_files = False

        if name == "web_search":
            category = "research"
        elif name.startswith("workspace_"):
            category = "workspace"
            requires_workspace = True
            writes_files = name in {
                "workspace_create_directory",
                "workspace_write_text_file",
                "workspace_patch_text_file",
                "workspace_delete_file",
            }
        elif name.startswith("unity_"):
            category = "unity"
            workspace_kind = "unity"
            requires_workspace = True
        elif name.startswith("engine_"):
            category = "engine_mcp"
            writes_files = name in {
                "engine_create_object",
                "engine_move_object",
                "engine_save_scene",
                "engine_run_project",
                "engine_create_script",
            }

        catalog.append(
            {
                "name": name,
                "description": str(fn.get("description", "") or "").strip(),
                "category": category,
                "workspace_kind": workspace_kind,
                "requires_workspace": requires_workspace,
                "writes_files": writes_files,
            }
        )
    return catalog


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
    tool_name: str,
    args: Dict[str, Any],
    project_id: Optional[str] = None,
    tool_event_handler: Optional[Callable[[Dict[str, Any]], None]] = None,
) -> str:
    try:
        if tool_name == "web_search":
            return web_search(args.get("query", ""))

        if tool_name == "workspace_read_files_batch":
            return workspace_read_files_batch(
                paths=args.get("paths", []),
                workspace_id=args.get("workspace_id"),
                project_id=project_id,
                max_chars_per_file=args.get("max_chars_per_file", 12000),
                max_total_chars=args.get("max_total_chars", 40000),
            )

        if tool_name == "workspace_create_directory":
            return workspace_create_directory(
                path=args.get("path", ""),
                workspace_id=args.get("workspace_id"),
                project_id=project_id,
                tool_event_handler=tool_event_handler,
            )

        if tool_name == "workspace_write_text_file":
            return workspace_write_text_file(
                path=args.get("path", ""),
                content=args.get("content", ""),
                workspace_id=args.get("workspace_id"),
                project_id=project_id,
                tool_event_handler=tool_event_handler,
            )

        if tool_name == "workspace_patch_text_file":
            return workspace_patch_text_file(
                path=args.get("path", ""),
                patches=args.get("patches", []),
                workspace_id=args.get("workspace_id"),
                project_id=project_id,
                tool_event_handler=tool_event_handler,
            )

        if tool_name == "workspace_delete_file":
            return workspace_delete_file(
                path=args.get("path", ""),
                workspace_id=args.get("workspace_id"),
                project_id=project_id,
                tool_event_handler=tool_event_handler,
            )

        if tool_name == "unity_list_dir":
            return unity_list_dir(
                relative_path=args.get("relative_path", ""),
                max_entries=args.get("max_entries", 200),
                project_id=project_id,
                workspace_id=args.get("workspace_id"),
            )

        if tool_name == "unity_read_file":
            return unity_read_file(
                relative_path=args.get("relative_path", ""),
                max_chars=args.get("max_chars", 12000),
                project_id=project_id,
                workspace_id=args.get("workspace_id"),
            )

        if tool_name == "unity_find_files":
            return unity_find_files(
                pattern=args.get("pattern", "*.cs"),
                relative_path=args.get("relative_path", ""),
                max_results=args.get("max_results", 200),
                project_id=project_id,
                workspace_id=args.get("workspace_id"),
            )

        if tool_name.startswith("engine_"):
            return dispatch_engine_tool_call(
                tool_name,
                args,
                project_id=project_id,
                tool_event_handler=tool_event_handler,
            )
    except (UnityToolError, WorkspaceAccessError, McpClientError):
        raise

    raise RuntimeError(f"[TOOL_ERROR:TOOL_NOT_FOUND] Tool '{tool_name}' not found.")
