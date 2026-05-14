"""Godot-specific MCP adapter.

Coding-Solo Godot MCP exposes project-level tools such as `get_project_info`,
`create_scene`, `add_node`, `save_scene`, and `run_project`. This adapter maps
Ludens' stable `engine_*` capabilities onto those concrete tools.
"""

from __future__ import annotations

from typing import Any, Dict

from ludens_flow.capabilities.mcp.adapters.base import BaseEngineAdapter, EngineMcpCall
from ludens_flow.capabilities.mcp.adapters.godot_schema import validate_godot_args
from ludens_flow.capabilities.mcp.health import McpClientError


class GodotEngineAdapter(BaseEngineAdapter):
    engine = "godot"
    operation_names = {
        "engine_list_scene": "godot.project.inspect",
        "engine_create_object": "godot.scene.node.create",
        "engine_move_object": "godot.scene.node.transform",
        "engine_save_scene": "godot.scene.save",
        "engine_read_console": "godot.debug.read",
        "engine_run_project": "godot.project.run",
        "engine_create_script": "godot.script.create",
    }
    tool_candidates = {
        "engine_list_scene": ["get_project_info"],
        "engine_create_object": ["add_node", "create_scene"],
        "engine_move_object": ["set_node_properties", "update_node", "move_node"],
        "engine_save_scene": ["save_scene"],
        "engine_read_console": ["get_debug_output"],
        "engine_run_project": ["run_project", "launch_editor", "stop_project"],
        "engine_create_script": ["create_script", "create_gdscript"],
    }

    def map_call(
        self,
        capability: str,
        args: Dict[str, Any],
        available_tools: list[dict],
        *,
        project_id: str | None = None,
    ) -> EngineMcpCall | None:
        validated_args = validate_godot_args(capability, args, project_id=project_id)
        validated_args["_godot_validated"] = True
        tool_name = self._select_tool_for_validated_args(capability, validated_args, available_tools)
        if not tool_name:
            return None
        tool_schema = next(
            (tool for tool in available_tools if str(tool.get("name") or "") == tool_name),
            {},
        )
        return EngineMcpCall(
            tool_name=tool_name,
            arguments=self.to_underlying_arguments(
                capability,
                validated_args,
                tool_name,
                tool_schema=tool_schema,
                project_id=project_id,
            ),
            operation_name=self.operation_name(capability),
        )

    def to_underlying_arguments(
        self,
        capability: str,
        args: Dict[str, Any],
        tool_name: str,
        *,
        tool_schema: dict | None = None,
        project_id: str | None = None,
    ) -> Dict[str, Any]:
        validated_args = (
            args
            if args.get("_godot_validated")
            else validate_godot_args(capability, args, project_id=project_id)
        )
        if capability == "engine_list_scene":
            return {"projectPath": validated_args.get("project_path")}
        if capability == "engine_read_console":
            return {}
        if capability == "engine_create_object":
            return _create_object_arguments(validated_args, tool_name)
        if capability == "engine_move_object":
            return _move_object_arguments(validated_args)
        if capability == "engine_save_scene":
            return _save_scene_arguments(validated_args)
        if capability == "engine_run_project":
            return _run_project_arguments(validated_args, tool_name)
        if capability == "engine_create_script":
            return _create_script_arguments(validated_args)
        raise McpClientError(f"Godot adapter cannot translate capability: {capability}")

    def _select_tool_for_validated_args(
        self,
        capability: str,
        args: Dict[str, Any],
        available_tools: list[dict],
    ) -> str:
        names = {str(tool.get("name") or "") for tool in available_tools}
        if capability == "engine_create_object":
            if args.get("create_scene"):
                return "create_scene" if "create_scene" in names else ""
            if "add_node" in names:
                return "add_node"
            return "create_scene" if "create_scene" in names else ""
        if capability == "engine_run_project":
            mode = str(args.get("mode") or "run").strip().lower()
            if mode == "stop":
                return "stop_project" if "stop_project" in names else ""
            if mode in {"launch_editor", "editor"}:
                return "launch_editor" if "launch_editor" in names else ""
            return "run_project" if "run_project" in names else ""
        return self.select_underlying_tool(capability, available_tools)


def _create_object_arguments(args: Dict[str, Any], tool_name: str) -> Dict[str, Any]:
    if tool_name == "create_scene":
        return {
            "projectPath": args.get("project_path"),
            "scenePath": args.get("scene_path"),
            "rootNodeType": args.get("root_node_type") or args.get("object_type") or "Node2D",
        }
    properties = dict(args.get("properties") or {})
    for field in ("position", "rotation", "scale"):
        if args.get(field) is not None and field not in properties:
            properties[field] = args.get(field)
    payload: Dict[str, Any] = {
        "projectPath": args.get("project_path"),
        "scenePath": args.get("scene_path"),
        "parentNodePath": args.get("parent") or "root",
        "nodeType": args.get("object_type") or "Node2D",
        "nodeName": args.get("name"),
        "properties": properties or None,
    }
    return _drop_none(payload)


def _move_object_arguments(args: Dict[str, Any]) -> Dict[str, Any]:
    properties: Dict[str, Any] = {}
    for field in ("position", "rotation", "scale"):
        if args.get(field) is not None:
            properties[field] = args.get(field)
    return {
        "projectPath": args.get("project_path"),
        "scenePath": args.get("scene_path"),
        "nodePath": args.get("target"),
        "properties": properties,
    }


def _save_scene_arguments(args: Dict[str, Any]) -> Dict[str, Any]:
    return _drop_none(
        {
            "projectPath": args.get("project_path"),
            "scenePath": args.get("scene_path"),
            "newPath": args.get("new_path"),
        }
    )


def _run_project_arguments(args: Dict[str, Any], tool_name: str) -> Dict[str, Any]:
    if tool_name == "stop_project":
        return {}
    payload: Dict[str, Any] = {"projectPath": args.get("project_path")}
    if tool_name == "run_project" and args.get("scene_path"):
        payload["scene"] = args.get("scene_path")
    return payload


def _create_script_arguments(args: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "projectPath": args.get("project_path"),
        "path": args.get("path"),
        "contents": args.get("content", ""),
    }


def _drop_none(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {key: value for key, value in payload.items() if value is not None}
