"""Unity-specific MCP adapter.

CoplayDev Unity MCP exposes broad tools such as `manage_scene` and
`manage_gameobject`. This adapter keeps Ludens capabilities stable while
translating them into Unity-native action payloads.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from ludens_flow.capabilities.mcp.adapters.base import BaseEngineAdapter, EngineMcpCall
from ludens_flow.capabilities.mcp.adapters.unity_schema import validate_unity_args
from ludens_flow.capabilities.mcp.health import McpClientError


class UnityEngineAdapter(BaseEngineAdapter):
    engine = "unity"
    operation_names = {
        "engine_list_scene": "unity.scene.inspect",
        "engine_create_object": "unity.object.create",
        "engine_move_object": "unity.object.transform",
        "engine_save_scene": "unity.scene.save",
        "engine_read_console": "unity.console.read",
        "engine_run_project": "unity.playmode.run",
        "engine_create_script": "unity.script.create",
    }
    tool_candidates = {
        "engine_list_scene": ["manage_scene"],
        "engine_create_object": ["manage_gameobject"],
        "engine_move_object": ["manage_gameobject"],
        "engine_save_scene": ["manage_scene"],
        "engine_read_console": ["read_console"],
        "engine_run_project": ["manage_editor", "run_tests"],
        "engine_create_script": ["create_script", "manage_script"],
    }

    def map_call(
        self,
        capability: str,
        args: Dict[str, Any],
        available_tools: list[dict],
        *,
        project_id: str | None = None,
    ) -> EngineMcpCall | None:
        validated_args = validate_unity_args(capability, args, project_id=project_id)
        validated_args["_unity_validated"] = True
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
            if args.get("_unity_validated")
            else validate_unity_args(capability, args, project_id=project_id)
        )
        if capability == "engine_list_scene":
            return {
                "action": "get_hierarchy",
                "page_size": validated_args.get("max_items", 200),
                "include_transform": True,
            }
        if capability == "engine_read_console":
            return _drop_none(
                {
                    "action": "get",
                    "types": ["all"],
                    "count": validated_args.get("max_entries", 50),
                    "filter_text": validated_args.get("filter"),
                    "format": "detailed",
                    "include_stacktrace": False,
                }
            )
        if capability == "engine_create_script":
            if tool_name == "manage_script":
                name, directory = _split_assets_file_path(str(validated_args.get("path") or ""))
                return _drop_none(
                    {
                        "action": "create",
                        "name": name,
                        "path": directory,
                        "contents": validated_args.get("content", ""),
                        "script_type": validated_args.get("script_type") or validated_args.get("language"),
                        "namespace": validated_args.get("namespace"),
                    }
                )
            return _drop_none(
                {
                    "path": validated_args.get("path"),
                    "contents": validated_args.get("content", ""),
                    "script_type": validated_args.get("script_type") or validated_args.get("language"),
                    "namespace": validated_args.get("namespace"),
                }
            )
        if capability == "engine_create_object":
            return _create_object_arguments(validated_args)
        if capability == "engine_move_object":
            return _move_object_arguments(validated_args)
        if capability == "engine_save_scene":
            return _save_scene_arguments(validated_args)
        if capability == "engine_run_project":
            return _run_project_arguments(validated_args, tool_name)
        raise McpClientError(f"Unity adapter cannot translate capability: {capability}")

    def _select_tool_for_validated_args(
        self,
        capability: str,
        args: Dict[str, Any],
        available_tools: list[dict],
    ) -> str:
        names = {str(tool.get("name") or "") for tool in available_tools}
        if capability == "engine_run_project":
            mode = str(args.get("mode") or "play").strip().lower()
            if mode in {"test", "tests", "editmode_tests", "playmode_tests"}:
                return "run_tests" if "run_tests" in names else ""
            return "manage_editor" if "manage_editor" in names else ""
        return self.select_underlying_tool(capability, available_tools)


def _create_object_arguments(args: Dict[str, Any]) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "action": "create",
        "name": args.get("name"),
        "parent": args.get("parent"),
        "position": args.get("position"),
        "rotation": args.get("rotation"),
        "scale": args.get("scale"),
        "tag": args.get("tag"),
        "layer": args.get("layer"),
        "components_to_add": args.get("components_to_add"),
    }
    object_type = str(args.get("object_type") or "empty").strip().lower()
    if object_type == "prefab":
        payload["prefab_path"] = args.get("prefab_path")
    elif object_type != "empty":
        payload["primitive_type"] = object_type.title()
    return {key: value for key, value in payload.items() if value is not None}


def _move_object_arguments(args: Dict[str, Any]) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "action": "modify",
        "target": args.get("target"),
        "search_method": args.get("search_method"),
        "name": args.get("new_name"),
        "parent": args.get("parent"),
        "position": args.get("position"),
        "rotation": args.get("rotation"),
        "scale": args.get("scale"),
        "tag": args.get("tag"),
        "layer": args.get("layer"),
        "set_active": args.get("set_active"),
        "components_to_add": args.get("components_to_add"),
        "components_to_remove": args.get("components_to_remove"),
        "component_properties": args.get("component_properties"),
    }
    return {key: value for key, value in payload.items() if value is not None}


def _save_scene_arguments(args: Dict[str, Any]) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"action": "save"}
    scene_path = str(args.get("scene_path") or "").strip()
    if scene_path:
        name, directory = _split_assets_file_path(scene_path)
        payload["name"] = name
        payload["path"] = directory
    return payload


def _run_project_arguments(args: Dict[str, Any], tool_name: str) -> Dict[str, Any]:
    mode = str(args.get("mode") or "play").strip().lower()
    if tool_name == "run_tests":
        unity_mode = "PlayMode" if mode == "playmode_tests" else "EditMode"
        return {
            "mode": unity_mode,
            "include_failed_tests": True,
            "include_details": False,
        }
    action = {
        "play": "play",
        "play_mode": "play",
        "stop": "stop",
        "pause": "pause",
    }.get(mode)
    if not action:
        raise McpClientError(f"Unity run mode `{mode}` requires `run_tests`, but that MCP tool is unavailable.")
    return {"action": action}


def _split_assets_file_path(path: str) -> tuple[str, str]:
    normalized = str(path or "").replace("\\", "/").strip().strip("/")
    if not normalized.lower().startswith("assets/"):
        raise McpClientError("Unity MCP paths must be Assets-relative.")
    name = Path(normalized).stem
    directory = Path(normalized).parent.as_posix()
    return name, directory


def _drop_none(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {key: value for key, value in payload.items() if value is not None}
