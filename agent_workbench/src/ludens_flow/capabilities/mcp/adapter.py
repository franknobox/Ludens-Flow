"""Whitelisted game-engine MCP adapter.

Agents only see the `engine_*` tools defined here. The adapter maps those
stable Ludens capabilities to a configured external MCP server and never
exposes raw external MCP tool names directly to agents.
"""

from __future__ import annotations

import json
import re
from typing import Any, Callable, Dict, List, Optional

from ludens_flow.capabilities.mcp.health import (
    McpClientError,
    call_mcp_tool,
    check_mcp_connection,
)
from ludens_flow.core.paths import get_project_mcp_connections, get_project_settings


ToolEventHandler = Optional[Callable[[dict[str, Any]], Any]]

ENGINE_NAMES = ["unity", "godot", "blender", "unreal"]
WRITE_CAPABILITIES = {
    "engine_create_object",
    "engine_move_object",
    "engine_save_scene",
    "engine_run_project",
    "engine_create_script",
}

ENGINE_TOOL_CANDIDATES: Dict[str, Dict[str, List[str]]] = {
    "unity": {
        "engine_list_scene": [
            "get_scene_hierarchy",
            "get_current_scene_hierarchy",
            "list_scene",
            "list_gameobjects",
            "get_hierarchy",
        ],
        "engine_create_object": [
            "create_gameobject",
            "create_object",
            "create_prefab",
            "add_gameobject",
        ],
        "engine_move_object": [
            "move_gameobject",
            "set_transform",
            "modify_gameobject",
            "update_transform",
        ],
        "engine_save_scene": ["save_scene", "save_current_scene"],
        "engine_read_console": [
            "read_console",
            "get_console_logs",
            "get_logs",
            "get_log_entries",
        ],
        "engine_run_project": ["start_play_mode", "run_tests", "play_unity_game"],
        "engine_create_script": ["create_script", "create_csharp_script"],
    },
    "godot": {
        "engine_list_scene": ["get_project_info", "get_scene_tree", "list_scenes"],
        "engine_create_object": ["add_node", "create_scene"],
        "engine_move_object": ["set_node_properties", "update_node", "move_node"],
        "engine_save_scene": ["save_scene"],
        "engine_read_console": ["get_debug_output"],
        "engine_run_project": ["run_project", "launch_editor"],
        "engine_create_script": ["create_script", "create_gdscript"],
    },
    "blender": {
        "engine_list_scene": ["get_scene_info", "get_scene_objects"],
        "engine_create_object": ["create_object", "add_object"],
        "engine_move_object": ["modify_object", "set_object_transform"],
        "engine_save_scene": ["save_file", "save_blend_file"],
        "engine_read_console": ["get_logs", "get_console_output"],
        "engine_run_project": ["render_scene"],
        "engine_create_script": ["run_script", "execute_blender_code"],
    },
    "unreal": {
        "engine_list_scene": ["list_actors", "get_scene_hierarchy", "get_level_actors"],
        "engine_create_object": ["spawn_actor", "create_actor"],
        "engine_move_object": ["set_actor_transform", "move_actor"],
        "engine_save_scene": ["save_level", "save_scene"],
        "engine_read_console": ["get_output_log", "read_console"],
        "engine_run_project": ["play_in_editor", "run_project"],
        "engine_create_script": ["create_blueprint", "create_cpp_class"],
    },
}


def _enum_schema(description: str) -> dict:
    return {"type": "string", "enum": ENGINE_NAMES, "description": description}


def _base_properties() -> dict:
    return {
        "engine": _enum_schema("Target engine MCP connection."),
        "connection_id": {
            "type": "string",
            "description": "Optional project MCP connection id. Required when multiple connections of the same engine exist.",
        },
    }


ENGINE_LIST_SCENE_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "engine_list_scene",
        "description": "Whitelisted engine.list_scene capability. Lists scene hierarchy or project scene information through a configured engine MCP.",
        "parameters": {
            "type": "object",
            "properties": {
                **_base_properties(),
                "scene_path": {"type": "string"},
                "max_items": {"type": "integer", "default": 200},
            },
            "required": ["engine"],
        },
    },
}

ENGINE_CREATE_OBJECT_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "engine_create_object",
        "description": "Whitelisted engine.create_object capability. Creates a scene object/node/actor through a configured engine MCP.",
        "parameters": {
            "type": "object",
            "properties": {
                **_base_properties(),
                "name": {"type": "string"},
                "object_type": {"type": "string"},
                "parent": {"type": "string"},
                "position": {"type": "object"},
                "properties": {"type": "object"},
            },
            "required": ["engine", "name"],
        },
    },
}

ENGINE_MOVE_OBJECT_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "engine_move_object",
        "description": "Whitelisted engine.move_object capability. Moves or updates transform for a scene object/node/actor.",
        "parameters": {
            "type": "object",
            "properties": {
                **_base_properties(),
                "target": {"type": "string"},
                "position": {"type": "object"},
                "rotation": {"type": "object"},
                "scale": {"type": "object"},
            },
            "required": ["engine", "target"],
        },
    },
}

ENGINE_SAVE_SCENE_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "engine_save_scene",
        "description": "Whitelisted engine.save_scene capability. Saves the current or specified scene through engine MCP.",
        "parameters": {
            "type": "object",
            "properties": {
                **_base_properties(),
                "scene_path": {"type": "string"},
            },
            "required": ["engine"],
        },
    },
}

ENGINE_READ_CONSOLE_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "engine_read_console",
        "description": "Whitelisted engine.read_console capability. Reads logs, console output, or debug output through engine MCP.",
        "parameters": {
            "type": "object",
            "properties": {
                **_base_properties(),
                "max_entries": {"type": "integer", "default": 200},
                "filter": {"type": "string"},
            },
            "required": ["engine"],
        },
    },
}

ENGINE_RUN_PROJECT_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "engine_run_project",
        "description": "Whitelisted engine.run_project capability. Runs or starts play mode through engine MCP.",
        "parameters": {
            "type": "object",
            "properties": {
                **_base_properties(),
                "project_path": {"type": "string"},
                "scene_path": {"type": "string"},
                "mode": {"type": "string"},
            },
            "required": ["engine"],
        },
    },
}

ENGINE_CREATE_SCRIPT_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "engine_create_script",
        "description": "Whitelisted engine.create_script capability. Creates a script through a configured engine MCP.",
        "parameters": {
            "type": "object",
            "properties": {
                **_base_properties(),
                "path": {"type": "string"},
                "class_name": {"type": "string"},
                "language": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["engine", "path"],
        },
    },
}

ENGINE_TOOL_SCHEMAS = [
    ENGINE_LIST_SCENE_TOOL_SCHEMA,
    ENGINE_CREATE_OBJECT_TOOL_SCHEMA,
    ENGINE_MOVE_OBJECT_TOOL_SCHEMA,
    ENGINE_SAVE_SCENE_TOOL_SCHEMA,
    ENGINE_READ_CONSOLE_TOOL_SCHEMA,
    ENGINE_RUN_PROJECT_TOOL_SCHEMA,
    ENGINE_CREATE_SCRIPT_TOOL_SCHEMA,
]


def list_engine_capability_tools() -> List[dict]:
    catalog = []
    for tool in ENGINE_TOOL_SCHEMAS:
        fn = tool["function"]
        name = fn["name"]
        catalog.append(
            {
                "name": name,
                "description": fn.get("description", ""),
                "category": "engine_mcp",
                "workspace_kind": None,
                "requires_workspace": False,
                "writes_files": name in WRITE_CAPABILITIES,
            }
        )
    return catalog


def dispatch_engine_tool_call(
    tool_name: str,
    args: Dict[str, Any],
    *,
    project_id: Optional[str],
    tool_event_handler: ToolEventHandler = None,
) -> str:
    if tool_name not in {tool["function"]["name"] for tool in ENGINE_TOOL_SCHEMAS}:
        raise RuntimeError(f"[TOOL_ERROR:ENGINE_TOOL_NOT_FOUND] Unknown engine tool: {tool_name}")

    engine = _normalize_engine(args.get("engine"))
    connection = _select_connection(project_id, engine, args.get("connection_id"))
    _ensure_permission(
        tool_name,
        args,
        project_id=project_id,
        tool_event_handler=tool_event_handler,
    )

    _emit(tool_event_handler, {"type": "tool_started", "tool_name": tool_name, "args": args})
    status = check_mcp_connection(connection)
    available_tools = status.get("tools") or []
    if status.get("status") not in {"tools_loaded", "reachable"}:
        raise McpClientError(status.get("message") or "MCP connection is not reachable.")

    raw_tool_name = _select_underlying_tool(engine, tool_name, available_tools)
    if not raw_tool_name:
        available = ", ".join(tool.get("name", "") for tool in available_tools[:30])
        raise McpClientError(
            f"No mapped MCP tool for {engine}.{tool_name}. Available tools: {available}"
        )

    _emit(
        tool_event_handler,
        {
            "type": "tool_progress",
            "tool_name": tool_name,
            "args": args,
            "message": f"Calling {engine} MCP tool: {raw_tool_name}",
        },
    )
    result = call_mcp_tool(connection, raw_tool_name, _to_underlying_arguments(args))
    text = _format_tool_result(result)
    _emit(
        tool_event_handler,
        {
            "type": "tool_completed",
            "tool_name": tool_name,
            "args": args,
            "result": text,
        },
    )
    return text


def _normalize_engine(value: Any) -> str:
    engine = str(value or "").strip().lower()
    if engine == "ue":
        engine = "unreal"
    if engine not in ENGINE_NAMES:
        raise RuntimeError(f"[TOOL_ERROR:ENGINE_REQUIRED] Unsupported engine: {value}")
    return engine


def _select_connection(project_id: Optional[str], engine: str, connection_id: Any) -> dict:
    requested_id = str(connection_id or "").strip()
    connections = [
        item
        for item in get_project_mcp_connections(project_id=project_id)
        if item.get("engine") == engine and item.get("enabled", True)
    ]
    if requested_id:
        connections = [item for item in connections if item.get("id") == requested_id]
    if not connections:
        raise McpClientError(f"No enabled {engine} MCP connection is configured for this project.")
    if len(connections) > 1:
        ids = ", ".join(item.get("id", "") for item in connections)
        raise McpClientError(f"Multiple {engine} MCP connections are configured. Specify connection_id: {ids}")
    return connections[0]


def _ensure_permission(
    tool_name: str,
    args: dict,
    *,
    project_id: Optional[str],
    tool_event_handler: ToolEventHandler,
) -> None:
    if tool_name not in WRITE_CAPABILITIES:
        return

    settings = get_project_settings(project_id=project_id)
    if not settings.get("agent_file_write_enabled", True):
        raise McpClientError("Project-level agent write/operation permission is disabled.")

    approved = _emit(
        tool_event_handler,
        {
            "type": "permission_required",
            "tool_name": tool_name,
            "args": args,
            "message": f"Engine MCP operation requires permission: {tool_name}",
        },
    )
    if approved is False:
        _emit(
            tool_event_handler,
            {
                "type": "permission_denied",
                "tool_name": tool_name,
                "args": args,
                "message": f"Permission denied for engine operation: {tool_name}",
            },
        )
        raise McpClientError("User denied this engine MCP operation.")

    _emit(
        tool_event_handler,
        {
            "type": "permission_granted",
            "tool_name": tool_name,
            "args": args,
            "message": f"Permission granted for engine operation: {tool_name}",
        },
    )


def _select_underlying_tool(engine: str, capability: str, available_tools: List[dict]) -> str:
    names = [str(tool.get("name") or "") for tool in available_tools]
    candidates = ENGINE_TOOL_CANDIDATES.get(engine, {}).get(capability, [])
    normalized_names = {_normalize_tool_name(name): name for name in names}

    for candidate in candidates:
        if candidate in names:
            return candidate
        normalized = _normalize_tool_name(candidate)
        if normalized in normalized_names:
            return normalized_names[normalized]

    capability_hint = capability.removeprefix("engine_")
    for name in names:
        normalized = _normalize_tool_name(name)
        if _normalize_tool_name(capability_hint) in normalized:
            return name
    return ""


def _normalize_tool_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _to_underlying_arguments(args: Dict[str, Any]) -> Dict[str, Any]:
    return {
        key: value
        for key, value in args.items()
        if key not in {"engine", "connection_id"} and value is not None
    }


def _format_tool_result(result: dict) -> str:
    content = result.get("content")
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if not isinstance(item, dict):
                continue
            if item.get("type") == "text":
                parts.append(str(item.get("text") or ""))
            elif "text" in item:
                parts.append(str(item.get("text") or ""))
        if parts:
            return "\n".join(parts).strip()
    return json.dumps(result, ensure_ascii=False, indent=2)


def _emit(event_handler: ToolEventHandler, payload: dict[str, Any]) -> Any:
    if event_handler:
        return event_handler(payload)
    return None

