"""Blender-specific MCP adapter.

Blender MCP exposes broad tools such as `execute_blender_code`. This adapter
keeps Ludens capabilities stable while translating them into Blender-native
operations and arguments.
"""

from __future__ import annotations

import json
from typing import Any, Dict

from ludens_flow.capabilities.mcp.adapters.base import BaseEngineAdapter
from ludens_flow.capabilities.mcp.adapters.blender_schema import (
    validate_blender_args,
)
from ludens_flow.capabilities.mcp.health import McpClientError


class BlenderEngineAdapter(BaseEngineAdapter):
    engine = "blender"
    operation_names = {
        "engine_list_scene": "blender.scene.inspect",
        "engine_create_object": "blender.object.create",
        "engine_move_object": "blender.object.transform",
        "engine_save_scene": "blender.file.save",
        "engine_read_console": "blender.console.read",
        "engine_run_project": "blender.viewport.capture",
        "engine_create_script": "blender.python.execute",
    }
    tool_candidates = {
        "engine_list_scene": ["get_scene_info", "get_scene_objects"],
        "engine_create_object": ["create_object", "add_object", "execute_blender_code"],
        "engine_move_object": ["modify_object", "set_object_transform", "execute_blender_code"],
        "engine_save_scene": ["save_file", "save_blend_file", "execute_blender_code"],
        "engine_read_console": ["get_logs", "get_console_output"],
        "engine_run_project": ["render_scene", "get_viewport_screenshot", "execute_blender_code"],
        "engine_create_script": ["run_script", "execute_blender_code"],
    }

    def to_underlying_arguments(
        self,
        capability: str,
        args: Dict[str, Any],
        tool_name: str,
        *,
        tool_schema: dict | None = None,
        project_id: str | None = None,
    ) -> Dict[str, Any]:
        validated_args = validate_blender_args(capability, args, project_id=project_id)
        if tool_name in {"get_scene_info", "get_scene_objects"}:
            return _inspect_scene_arguments(
                tool_schema,
                _user_prompt(validated_args, self.operation_name(capability)),
                validated_args.get("max_items"),
            )
        if tool_name == "get_viewport_screenshot":
            return {
                "max_size": _coerce_int(validated_args.get("max_size"), default=1000),
                "user_prompt": _user_prompt(validated_args, self.operation_name(capability)),
            }
        if tool_name == "execute_blender_code":
            return {
                "code": _build_blender_python(capability, validated_args),
                "user_prompt": _user_prompt(validated_args, self.operation_name(capability)),
            }
        return super().to_underlying_arguments(
                capability,
                validated_args,
                tool_name,
                tool_schema=tool_schema,
                project_id=project_id,
            )

    def fallback_arguments(
        self,
        capability: str,
        tool_name: str,
        arguments: Dict[str, Any],
    ) -> list[Dict[str, Any]]:
        if capability != "engine_list_scene" or tool_name not in {"get_scene_info", "get_scene_objects"}:
            return []
        if set(arguments) == {"user_prompt"}:
            return [{}]
        return []


def _build_blender_python(capability: str, args: Dict[str, Any]) -> str:
    if capability == "engine_create_object":
        return _build_create_object_python(args)
    if capability == "engine_move_object":
        return _build_move_object_python(args)
    if capability == "engine_save_scene":
        return _build_save_scene_python(args)
    if capability == "engine_run_project":
        return _build_run_project_python(args)
    if capability == "engine_create_script":
        content = str(args.get("content") or args.get("code") or "").strip()
        if not content:
            raise McpClientError("Blender Python execution requires `content`.")
        return content
    raise McpClientError(f"Blender adapter cannot translate capability: {capability}")


def _inspect_scene_arguments(tool_schema: dict | None, user_prompt: str, max_items: Any) -> Dict[str, Any]:
    input_schema = tool_schema.get("inputSchema") if isinstance(tool_schema, dict) else None
    if not isinstance(input_schema, dict):
        return {}
    required = input_schema.get("required")
    properties = input_schema.get("properties")
    if not isinstance(properties, dict):
        return {}

    arguments: Dict[str, Any] = {}
    if "user_prompt" in properties:
        arguments["user_prompt"] = user_prompt
    if "max_items" in properties:
        arguments["max_items"] = max_items
    elif "limit" in properties:
        arguments["limit"] = max_items
    if isinstance(required, list) and "random_string" in required and "random_string" in properties:
        arguments["random_string"] = "ludens-flow"
    return arguments


def _build_create_object_python(args: Dict[str, Any]) -> str:
    name = str(args.get("name") or "").strip()
    if not name:
        raise McpClientError("Blender object creation requires `name`.")

    object_type = str(args.get("object_type") or "cube").strip().lower()
    position = _coerce_vector(args.get("position"), default=(0.0, 0.0, 0.0))
    properties = args.get("properties") if isinstance(args.get("properties"), dict) else {}
    size = _coerce_float(properties.get("size"), default=1.0)
    parent = str(args.get("parent") or properties.get("parent") or "").strip()

    op_lines = {
        "cube": [f"bpy.ops.mesh.primitive_cube_add(size={size}, location={_py(position)})"],
        "sphere": [f"bpy.ops.mesh.primitive_uv_sphere_add(radius={size / 2}, location={_py(position)})"],
        "uv_sphere": [f"bpy.ops.mesh.primitive_uv_sphere_add(radius={size / 2}, location={_py(position)})"],
        "ico_sphere": [f"bpy.ops.mesh.primitive_ico_sphere_add(radius={size / 2}, location={_py(position)})"],
        "cylinder": [f"bpy.ops.mesh.primitive_cylinder_add(radius={size / 2}, depth={size}, location={_py(position)})"],
        "cone": [f"bpy.ops.mesh.primitive_cone_add(radius1={size / 2}, depth={size}, location={_py(position)})"],
        "plane": [f"bpy.ops.mesh.primitive_plane_add(size={size}, location={_py(position)})"],
        "empty": [f"bpy.ops.object.empty_add(type='PLAIN_AXES', location={_py(position)})"],
        "camera": [f"bpy.ops.object.camera_add(location={_py(position)})"],
        "light": [_light_add_line(properties, position)],
        "point_light": [_light_add_line({**properties, "light_type": "POINT"}, position)],
        "sun": [_light_add_line({**properties, "light_type": "SUN"}, position)],
        "area_light": [_light_add_line({**properties, "light_type": "AREA"}, position)],
    }.get(object_type)
    if not op_lines:
        raise McpClientError(f"Unsupported Blender object_type: {object_type}")

    rotation = _coerce_vector(args.get("rotation") or properties.get("rotation"), default=None)
    scale = _coerce_vector(args.get("scale") or properties.get("scale"), default=None)

    lines = [
        "import bpy",
        *op_lines,
        "obj = bpy.context.object",
        f"obj.name = {_py(name)}",
    ]
    if rotation is not None:
        lines.append(f"obj.rotation_euler = {_py(rotation)}")
    if scale is not None:
        lines.append(f"obj.scale = {_py(scale)}")
    if parent:
        lines.extend(
            [
                f"parent = bpy.data.objects.get({_py(parent)})",
                "if parent is None:",
                f"    raise ValueError({_py(f'Parent object not found: {parent}')})",
                "obj.parent = parent",
            ]
        )
    lines.append("print(f'Created Blender object: {obj.name}')")
    return "\n".join(lines)


def _build_move_object_python(args: Dict[str, Any]) -> str:
    target = str(args.get("target") or args.get("name") or "").strip()
    if not target:
        raise McpClientError("Blender object transform requires `target`.")

    lines = [
        "import bpy",
        f"obj = bpy.data.objects.get({_py(target)})",
        "if obj is None:",
        f"    raise ValueError({_py(f'Blender object not found: {target}')})",
    ]
    position = _coerce_vector(args.get("position"), default=None)
    rotation = _coerce_vector(args.get("rotation"), default=None)
    scale = _coerce_vector(args.get("scale"), default=None)
    if position is not None:
        lines.append(f"obj.location = {_py(position)}")
    if rotation is not None:
        lines.append(f"obj.rotation_euler = {_py(rotation)}")
    if scale is not None:
        lines.append(f"obj.scale = {_py(scale)}")
    if position is None and rotation is None and scale is None:
        raise McpClientError("Blender object transform requires position, rotation, or scale.")
    lines.append("print(f'Updated Blender object transform: {obj.name}')")
    return "\n".join(lines)


def _build_save_scene_python(args: Dict[str, Any]) -> str:
    scene_path = str(args.get("scene_path") or "").strip()
    if scene_path:
        return "\n".join(
            [
                "import bpy",
                f"bpy.ops.wm.save_as_mainfile(filepath={_py(scene_path)})",
                f"print({_py(f'Saved Blender file to: {scene_path}')})",
            ]
        )
    if not bool(args.get("allow_current_file")):
        raise McpClientError(
            "Saving the current Blender file without `scene_path` requires `allow_current_file=true`."
        )
    return "\n".join(
        [
            "import bpy",
            "if not bpy.data.filepath:",
            "    raise ValueError('Current Blender file has no path. Provide scene_path to save as a new .blend file.')",
            "bpy.ops.wm.save_as_mainfile()",
            "print(f'Saved Blender file: {bpy.data.filepath}')",
        ]
    )


def _build_run_project_python(args: Dict[str, Any]) -> str:
    mode = str(args.get("mode") or "render_still").strip().lower()
    if mode in {"render", "render_still", "render_still_image"}:
        return "\n".join(
            [
                "import bpy",
                "bpy.ops.render.render(write_still=True)",
                "print('Blender render completed.')",
            ]
        )
    if mode in {"play_animation", "animation"}:
        return "\n".join(
            [
                "import bpy",
                "bpy.ops.screen.animation_play()",
                "print('Blender animation playback toggled.')",
            ]
        )
    raise McpClientError(f"Unsupported Blender run mode: {mode}")


def _light_add_line(properties: Dict[str, Any], position: tuple[float, float, float]) -> str:
    light_type = str(properties.get("light_type") or "POINT").strip().upper()
    if light_type not in {"POINT", "SUN", "SPOT", "AREA"}:
        light_type = "POINT"
    return f"bpy.ops.object.light_add(type={_py(light_type)}, location={_py(position)})"


def _user_prompt(args: Dict[str, Any], operation_name: str) -> str:
    return str(args.get("user_prompt") or f"Ludens-Flow {operation_name}").strip()


def _coerce_vector(value: Any, *, default: tuple[float, float, float] | None) -> tuple[float, float, float] | None:
    if value is None:
        return default
    if isinstance(value, dict):
        return (
            _coerce_float(value.get("x"), default=0.0),
            _coerce_float(value.get("y"), default=0.0),
            _coerce_float(value.get("z"), default=0.0),
        )
    if isinstance(value, (list, tuple)) and len(value) >= 3:
        return (
            _coerce_float(value[0], default=0.0),
            _coerce_float(value[1], default=0.0),
            _coerce_float(value[2], default=0.0),
        )
    return default


def _coerce_float(value: Any, *, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _coerce_int(value: Any, *, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _py(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)
