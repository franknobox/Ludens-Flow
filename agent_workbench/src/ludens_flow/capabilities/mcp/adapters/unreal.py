"""Unreal-specific MCP adapter definitions.

The chongdashu/unreal-mcp server exposes concrete Unreal Editor tools such as
`get_actors_in_level`, `spawn_actor`, `set_actor_transform`, and Blueprint
asset helpers. This adapter keeps Ludens-Flow's stable `engine_*` capability
surface while translating calls to those concrete tool names and payloads.
"""

from __future__ import annotations

import math
import re
from typing import Any, Dict

from ludens_flow.capabilities.mcp.adapters.base import BaseEngineAdapter, EngineMcpCall
from ludens_flow.capabilities.mcp.adapters.safe_schema import validate_safe_engine_args
from ludens_flow.capabilities.mcp.health import McpClientError


_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
_UNSUPPORTED_CAPABILITIES = {
    "engine_save_scene": "The current unreal-mcp repository does not expose a stable save-level tool.",
    "engine_read_console": "The current unreal-mcp repository does not expose a stable output-log tool.",
    "engine_run_project": "The current unreal-mcp repository does not expose a stable Play-In-Editor tool.",
}


class UnrealEngineAdapter(BaseEngineAdapter):
    engine = "unreal"
    operation_names = {
        "engine_list_scene": "unreal.level.actors",
        "engine_create_object": "unreal.actor.spawn",
        "engine_move_object": "unreal.actor.transform",
        "engine_save_scene": "unreal.level.save.unsupported",
        "engine_read_console": "unreal.output_log.read.unsupported",
        "engine_run_project": "unreal.pie.run.unsupported",
        "engine_create_script": "unreal.blueprint.asset",
    }
    tool_candidates = {
        "engine_list_scene": ["get_actors_in_level", "find_actors_by_name", "get_actor_properties"],
        "engine_create_object": ["spawn_actor", "spawn_blueprint_actor"],
        "engine_move_object": ["set_actor_transform", "set_actor_property"],
        "engine_save_scene": [],
        "engine_read_console": [],
        "engine_run_project": [],
        "engine_create_script": [
            "create_blueprint",
            "compile_blueprint",
            "add_component_to_blueprint",
            "set_blueprint_property",
            "create_input_mapping",
        ],
    }

    def map_call(
        self,
        capability: str,
        args: Dict[str, Any],
        available_tools: list[dict],
        *,
        project_id: str | None = None,
    ) -> EngineMcpCall | None:
        if capability in _UNSUPPORTED_CAPABILITIES:
            raise McpClientError(_UNSUPPORTED_CAPABILITIES[capability])

        validated_args = _validate_unreal_args(capability, args, project_id=project_id)
        validated_args["_unreal_validated"] = True
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
            if args.get("_unreal_validated")
            else _validate_unreal_args(capability, args, project_id=project_id)
        )
        if capability == "engine_list_scene":
            return _list_scene_arguments(validated_args, tool_name)
        if capability == "engine_create_object":
            return _create_object_arguments(validated_args, tool_name)
        if capability == "engine_move_object":
            return _move_object_arguments(validated_args, tool_name)
        if capability == "engine_create_script":
            return _blueprint_arguments(validated_args, tool_name)
        raise McpClientError(f"Unreal adapter cannot translate capability: {capability}")

    def _select_tool_for_validated_args(
        self,
        capability: str,
        args: Dict[str, Any],
        available_tools: list[dict],
    ) -> str:
        names = {str(tool.get("name") or "") for tool in available_tools}
        properties = dict(args.get("properties") or {})
        if capability == "engine_list_scene":
            if args.get("target") and "get_actor_properties" in names:
                return "get_actor_properties"
            if args.get("filter") and "find_actors_by_name" in names:
                return "find_actors_by_name"
            return "get_actors_in_level" if "get_actors_in_level" in names else ""
        if capability == "engine_create_object":
            if properties.get("blueprint_name") and "spawn_blueprint_actor" in names:
                return "spawn_blueprint_actor"
            if properties.get("blueprint_name"):
                return ""
            return "spawn_actor" if "spawn_actor" in names else ""
        if capability == "engine_move_object":
            if properties.get("property_name") and "set_actor_property" in names:
                return "set_actor_property"
            if properties.get("property_name"):
                return ""
            return "set_actor_transform" if "set_actor_transform" in names else ""
        if capability == "engine_create_script":
            action = str(args.get("action") or properties.get("action") or "create_blueprint").strip().lower()
            explicit_actions = {
                "compile": "compile_blueprint",
                "add_component": "add_component_to_blueprint",
                "set_property": "set_blueprint_property",
                "input_mapping": "create_input_mapping",
            }
            if action in explicit_actions:
                target = explicit_actions[action]
                return target if target in names else ""
            return "create_blueprint" if "create_blueprint" in names else ""
        return self.select_underlying_tool(capability, available_tools)


def _validate_unreal_args(
    capability: str,
    args: Dict[str, Any],
    *,
    project_id: str | None,
) -> Dict[str, Any]:
    if not isinstance(args, dict):
        raise McpClientError("Unreal tool arguments must be an object.")
    requested_engine = str(args.get("engine") or "").strip().lower()
    if requested_engine not in {"unreal", "ue"}:
        raise McpClientError("Unreal capability requires `engine` to be `unreal`.")
    if capability == "engine_create_script":
        return _validate_blueprint_args(args)
    return validate_safe_engine_args("unreal", capability, {**args, "engine": "unreal"}, project_id=project_id)


def _validate_blueprint_args(args: Dict[str, Any]) -> Dict[str, Any]:
    properties = dict(args.get("properties") or {})
    result: Dict[str, Any] = {
        key: value
        for key, value in args.items()
        if key not in {"engine", "connection_id"} and value is not None
    }
    action = str(result.get("action") or properties.get("action") or "create_blueprint").strip().lower()
    if action not in {"create_blueprint", "compile", "add_component", "set_property", "input_mapping"}:
        raise McpClientError(
            "Unreal Blueprint action must be create_blueprint, compile, add_component, set_property, or input_mapping."
        )
    result["action"] = action
    result["properties"] = properties

    if action == "input_mapping":
        result["action_name"] = _safe_label(result.get("action_name") or properties.get("action_name"), "action_name")
        result["key"] = _safe_label(result.get("key") or properties.get("key"), "key")
        result["input_type"] = _safe_label(result.get("input_type") or properties.get("input_type") or "Action", "input_type")
        return result

    blueprint_name = (
        result.get("blueprint_name")
        or properties.get("blueprint_name")
        or result.get("class_name")
        or result.get("name")
    )
    result["blueprint_name"] = _safe_label(blueprint_name, "blueprint_name")
    if action == "create_blueprint":
        result["parent_class"] = _safe_label(
            result.get("parent_class") or properties.get("parent_class") or "Actor",
            "parent_class",
        )
    elif action == "add_component":
        result["component_type"] = _safe_label(
            result.get("component_type") or properties.get("component_type"),
            "component_type",
        )
        result["component_name"] = _safe_label(
            result.get("component_name") or properties.get("component_name"),
            "component_name",
        )
        for field, default in (
            ("location", (0.0, 0.0, 0.0)),
            ("rotation", (0.0, 0.0, 0.0)),
            ("scale", (1.0, 1.0, 1.0)),
        ):
            result[field] = _vector3(result.get(field) or properties.get(field), field=field, default=default)
    elif action == "set_property":
        result["property_name"] = _safe_label(
            result.get("property_name") or properties.get("property_name"),
            "property_name",
        )
        if "property_value" not in result and "property_value" not in properties:
            raise McpClientError("Unreal Blueprint property update requires `property_value`.")
        result["property_value"] = result.get("property_value", properties.get("property_value"))
    return result


def _list_scene_arguments(args: Dict[str, Any], tool_name: str) -> Dict[str, Any]:
    if tool_name == "find_actors_by_name":
        return {"pattern": args.get("filter") or "*"}
    if tool_name == "get_actor_properties":
        return {"name": args.get("target")}
    return {}


def _create_object_arguments(args: Dict[str, Any], tool_name: str) -> Dict[str, Any]:
    properties = dict(args.get("properties") or {})
    if tool_name == "spawn_blueprint_actor":
        return {
            "blueprint_name": _safe_label(properties.get("blueprint_name"), "blueprint_name"),
            "actor_name": args.get("name"),
            "location": _vector3(args.get("position"), field="position", default=(0.0, 0.0, 0.0)),
            "rotation": _vector3(args.get("rotation"), field="rotation", default=(0.0, 0.0, 0.0)),
        }
    return {
        "name": args.get("name"),
        "type": _safe_label(args.get("object_type") or properties.get("type") or "StaticMeshActor", "type"),
        "location": _vector3(args.get("position"), field="position", default=(0.0, 0.0, 0.0)),
        "rotation": _vector3(args.get("rotation"), field="rotation", default=(0.0, 0.0, 0.0)),
    }


def _move_object_arguments(args: Dict[str, Any], tool_name: str) -> Dict[str, Any]:
    properties = dict(args.get("properties") or {})
    if tool_name == "set_actor_property":
        property_name = _safe_label(properties.get("property_name"), "property_name")
        if "property_value" not in properties:
            raise McpClientError("Unreal actor property update requires `properties.property_value`.")
        return {
            "name": args.get("target"),
            "property_name": property_name,
            "property_value": properties.get("property_value"),
        }
    payload: Dict[str, Any] = {"name": args.get("target")}
    for source, target in (("position", "location"), ("rotation", "rotation"), ("scale", "scale")):
        if args.get(source) is not None:
            payload[target] = _vector3(args.get(source), field=source, default=None)
    return payload


def _blueprint_arguments(args: Dict[str, Any], tool_name: str) -> Dict[str, Any]:
    if tool_name == "compile_blueprint":
        return {"blueprint_name": args.get("blueprint_name")}
    if tool_name == "add_component_to_blueprint":
        payload = {
            "blueprint_name": args.get("blueprint_name"),
            "component_type": args.get("component_type"),
            "component_name": args.get("component_name"),
            "location": args.get("location"),
            "rotation": args.get("rotation"),
            "scale": args.get("scale"),
            "component_properties": dict(args.get("properties") or {}).get("component_properties"),
        }
        return _drop_none(payload)
    if tool_name == "set_blueprint_property":
        return {
            "blueprint_name": args.get("blueprint_name"),
            "property_name": args.get("property_name"),
            "property_value": args.get("property_value"),
        }
    if tool_name == "create_input_mapping":
        return {
            "action_name": args.get("action_name"),
            "key": args.get("key"),
            "input_type": args.get("input_type") or "Action",
        }
    return {
        "name": args.get("blueprint_name"),
        "parent_class": args.get("parent_class") or "Actor",
    }


def _safe_label(value: Any, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise McpClientError(f"Unreal `{field}` is required.")
    if len(text) > 120:
        raise McpClientError(f"Unreal `{field}` is too long. Keep it under 120 characters.")
    if _CONTROL_CHAR_RE.search(text):
        raise McpClientError(f"Unreal `{field}` contains control characters.")
    return text


def _vector3(
    value: Any,
    *,
    field: str,
    default: tuple[float, float, float] | None,
) -> list[float] | None:
    if value is None:
        return list(default) if default is not None else None
    if isinstance(value, dict):
        raw = [value.get("x"), value.get("y"), value.get("z")]
    elif isinstance(value, (list, tuple)) and len(value) >= 3:
        raw = list(value[:3])
    else:
        raise McpClientError(f"Unreal `{field}` must be a vector object with x/y/z or a 3-item list.")
    return [_bounded_float(item, field=f"{field}.{index}") for index, item in enumerate(raw)]


def _bounded_float(value: Any, *, field: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = 0.0
    if not math.isfinite(number) or number < -100000.0 or number > 100000.0:
        raise McpClientError(f"Unreal `{field}` must be a finite number between -100000 and 100000.")
    return number


def _drop_none(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {key: value for key, value in payload.items() if value is not None}
