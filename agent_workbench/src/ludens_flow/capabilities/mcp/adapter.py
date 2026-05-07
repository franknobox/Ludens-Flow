"""Whitelisted game-engine MCP adapter.

Agents only see the `engine_*` tools defined here. The adapter maps those
stable Ludens capabilities to a configured external MCP server and never
exposes raw external MCP tool names directly to agents.
"""

from __future__ import annotations

import json
from typing import Any, Callable, Dict, List, Optional

from ludens_flow.capabilities.mcp.adapters import get_engine_adapter
from ludens_flow.capabilities.mcp.health import (
    McpClientError,
    call_mcp_tool,
    check_mcp_connection,
)
from ludens_flow.capabilities.paths import get_project_mcp_connections
from ludens_flow.core.paths import get_project_settings


ToolEventHandler = Optional[Callable[[dict[str, Any]], Any]]

ENGINE_NAMES = ["unity", "godot", "blender", "unreal"]
WRITE_CAPABILITIES = {
    "engine_create_object",
    "engine_move_object",
    "engine_save_scene",
    "engine_run_project",
    "engine_create_script",
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
                "workspace_id": {
                    "type": "string",
                    "description": "Optional approved workspace id. Required when multiple workspaces are available.",
                },
                "allow_current_file": {
                    "type": "boolean",
                    "description": "For Blender only: explicitly allow saving the currently opened .blend file when scene_path is omitted.",
                },
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
                "max_size": {
                    "type": "integer",
                    "description": "Optional viewport screenshot size for Blender-like tools.",
                },
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
            "required": ["engine"],
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

    status = check_mcp_connection(connection)
    available_tools = status.get("tools") or []
    transport = str(status.get("transport") or "").strip() or None
    if status.get("status") not in {"tools_loaded", "reachable"}:
        raise McpClientError(status.get("message") or "MCP connection is not reachable.")

    engine_adapter = get_engine_adapter(engine)
    mapped_call = engine_adapter.map_call(
        tool_name,
        args,
        available_tools,
        project_id=project_id,
    )
    if not mapped_call:
        available = ", ".join(tool.get("name", "") for tool in available_tools[:30])
        raise McpClientError(
            f"No mapped MCP tool for {engine}.{tool_name}. Available tools: {available}"
        )

    attempted_arguments = [mapped_call.arguments]
    try:
        result = call_mcp_tool(
            connection,
            mapped_call.tool_name,
            mapped_call.arguments,
            transport=transport,
        )
    except McpClientError as exc:
        if "Invalid request parameters" not in str(exc):
            raise
        last_error = exc
        for fallback_arguments in engine_adapter.fallback_arguments(
            tool_name,
            mapped_call.tool_name,
            mapped_call.arguments,
        ):
            attempted_arguments.append(fallback_arguments)
            try:
                result = call_mcp_tool(
                    connection,
                    mapped_call.tool_name,
                    fallback_arguments,
                    transport=transport,
                )
                break
            except McpClientError as retry_exc:
                last_error = retry_exc
        else:
            attempts = "; ".join(
                json.dumps(item, ensure_ascii=False, sort_keys=True)
                for item in attempted_arguments
            )
            raise McpClientError(f"{last_error} Tried arguments: {attempts}") from last_error
    text = _format_tool_result(result)
    if tool_name == "engine_list_scene":
        text = _limit_scene_result_text(text, _coerce_max_items(args.get("max_items")))
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
    if approved is not True:
        _emit(
            tool_event_handler,
            {
                "type": "permission_denied",
                "tool_name": tool_name,
                "args": args,
                "message": f"Permission denied for engine operation: {tool_name}",
            },
        )
        raise McpClientError("User denied this engine MCP operation, or no permission handler was available.")

    _emit(
        tool_event_handler,
        {
            "type": "permission_granted",
            "tool_name": tool_name,
            "args": args,
            "message": f"Permission granted for engine operation: {tool_name}",
        },
    )


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


def _coerce_max_items(value: Any) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return 200
    return max(1, min(parsed, 1000))


def _limit_scene_result_text(text: str, max_items: int) -> str:
    stripped = text.strip()
    if not stripped:
        return text
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError:
        lines = text.splitlines()
        if len(lines) <= max_items:
            return text
        omitted = len(lines) - max_items
        return "\n".join(lines[:max_items] + [f"... truncated {omitted} scene items by max_items={max_items}"])

    limiter = _SceneResultLimiter(max_items)
    limited = limiter.limit(payload)
    if limiter.omitted:
        if isinstance(limited, dict):
            limited["truncated"] = True
            limited["omitted_items"] = limiter.omitted
            limited["max_items"] = max_items
        else:
            limited = {
                "items": limited,
                "truncated": True,
                "omitted_items": limiter.omitted,
                "max_items": max_items,
            }
    return json.dumps(limited, ensure_ascii=False, indent=2)


class _SceneResultLimiter:
    def __init__(self, max_items: int):
        self.max_items = max_items
        self.seen = 0
        self.omitted = 0

    def limit(self, value: Any) -> Any:
        if isinstance(value, list):
            if not any(isinstance(item, (dict, list)) for item in value):
                return value
            result = []
            for item in value:
                if self.seen >= self.max_items:
                    self.omitted += 1
                    continue
                self.seen += 1
                result.append(self.limit(item))
            return result
        if isinstance(value, dict):
            return {key: self.limit(item) for key, item in value.items()}
        return value


def _emit(event_handler: ToolEventHandler, payload: dict[str, Any]) -> Any:
    if event_handler:
        return event_handler(payload)
    return None
