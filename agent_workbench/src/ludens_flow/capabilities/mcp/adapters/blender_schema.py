"""Blender MCP parameter schemas and safety validation."""

from __future__ import annotations

import math
from pathlib import Path
import re
from typing import Any, Dict, Iterable

from ludens_flow.capabilities.mcp.health import McpClientError
from ludens_flow.capabilities.workspaces import WorkspaceAccessError, resolve_workspace_target
from ludens_flow.core.paths import list_project_workspaces, resolve_project_id


BLENDER_OBJECT_TYPES = frozenset(
    {
        "cube",
        "sphere",
        "uv_sphere",
        "ico_sphere",
        "cylinder",
        "cone",
        "plane",
        "empty",
        "camera",
        "light",
        "point_light",
        "sun",
        "area_light",
    }
)

BLENDER_RUN_MODES = frozenset(
    {
        "render",
        "render_still",
        "render_still_image",
        "play_animation",
        "animation",
    }
)

BLENDER_CAPABILITY_SCHEMAS: Dict[str, Dict[str, Any]] = {
    "engine_list_scene": {
        "required": ["engine"],
        "properties": {
            "engine": {"const": "blender"},
            "max_items": {"type": "integer", "minimum": 1, "maximum": 1000},
        },
    },
    "engine_create_object": {
        "required": ["engine", "name"],
        "properties": {
            "engine": {"const": "blender"},
            "name": {"type": "string", "minLength": 1, "maxLength": 120},
            "object_type": {"enum": sorted(BLENDER_OBJECT_TYPES)},
            "position": {"type": "vector3"},
            "rotation": {"type": "vector3"},
            "scale": {"type": "vector3"},
            "parent": {"type": "string"},
            "properties": {"type": "object"},
        },
    },
    "engine_move_object": {
        "required": ["engine", "target"],
        "properties": {
            "engine": {"const": "blender"},
            "target": {"type": "string", "minLength": 1, "maxLength": 120},
            "position": {"type": "vector3"},
            "rotation": {"type": "vector3"},
            "scale": {"type": "vector3"},
        },
    },
    "engine_save_scene": {
        "required": ["engine"],
        "properties": {
            "engine": {"const": "blender"},
            "scene_path": {"type": "string", "suffix": ".blend"},
            "workspace_id": {"type": "string"},
            "allow_current_file": {"type": "boolean"},
        },
    },
    "engine_run_project": {
        "required": ["engine"],
        "properties": {
            "engine": {"const": "blender"},
            "mode": {"enum": sorted(BLENDER_RUN_MODES)},
            "max_size": {"type": "integer", "minimum": 256, "maximum": 2048},
        },
    },
    "engine_create_script": {
        "required": ["engine", "content"],
        "properties": {
            "engine": {"const": "blender"},
            "content": {"type": "string", "minLength": 1, "maxLength": 20000},
        },
    },
}

_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
_PATH_EXPANSION_RE = re.compile(r"^(~|%[^%]+%|\$[A-Za-z_][A-Za-z0-9_]*|\$\{.+\})")
_GLOB_RE = re.compile(r"[*?\[\]{}]")
_FORBIDDEN_PY_PATTERNS = [
    re.compile(pattern, re.IGNORECASE | re.MULTILINE)
    for pattern in [
        r"^\s*import\s+(os|sys|subprocess|shutil|socket|pathlib|requests|urllib|http|ftplib)\b",
        r"^\s*from\s+(os|sys|subprocess|shutil|socket|pathlib|requests|urllib|http|ftplib)\b",
        r"\b(__import__|eval|exec|compile|open)\s*\(",
        r"\bsubprocess\.",
        r"\bos\.",
        r"\bshutil\.",
        r"\bsocket\.",
        r"\bpathlib\.",
        r"\brequests\.",
        r"\burllib\.",
        r"\bhttp\.",
        r"\bftplib\.",
        r"\bbpy\.ops\.wm\.open_mainfile\s*\(",
        r"\bbpy\.ops\.wm\.quit_blender\s*\(",
    ]
]


def validate_blender_args(
    capability: str,
    args: Dict[str, Any],
    *,
    project_id: str | None = None,
) -> Dict[str, Any]:
    if capability not in BLENDER_CAPABILITY_SCHEMAS:
        raise McpClientError(f"Unsupported Blender capability schema: {capability}")
    if not isinstance(args, dict):
        raise McpClientError("Blender tool arguments must be an object.")

    normalized: Dict[str, Any] = dict(args)
    engine = str(normalized.get("engine") or "").strip().lower()
    if engine != "blender":
        raise McpClientError("Blender capability requires `engine` to be `blender`.")

    if capability == "engine_list_scene":
        normalized["max_items"] = _bounded_int(normalized.get("max_items"), default=200, minimum=1, maximum=1000)
    elif capability == "engine_create_object":
        normalized = _validate_create_object(normalized)
    elif capability == "engine_move_object":
        normalized = _validate_move_object(normalized)
    elif capability == "engine_save_scene":
        normalized = _validate_save_scene(normalized, project_id=project_id)
    elif capability == "engine_run_project":
        normalized = _validate_run_project(normalized)
    elif capability == "engine_create_script":
        normalized = _validate_script(normalized)
    return normalized


def _validate_create_object(args: Dict[str, Any]) -> Dict[str, Any]:
    result = dict(args)
    result["name"] = _safe_label(result.get("name"), field="name")
    object_type = str(result.get("object_type") or "cube").strip().lower()
    if object_type not in BLENDER_OBJECT_TYPES:
        raise McpClientError(
            f"Unsupported Blender object_type `{object_type}`. Allowed: {', '.join(sorted(BLENDER_OBJECT_TYPES))}."
        )
    result["object_type"] = object_type
    result["position"] = _vector3(result.get("position"), field="position", default=(0.0, 0.0, 0.0))
    if result.get("rotation") is not None:
        result["rotation"] = _vector3(result.get("rotation"), field="rotation", default=None)
    if result.get("scale") is not None:
        result["scale"] = _vector3(result.get("scale"), field="scale", default=None)
    if result.get("parent"):
        result["parent"] = _safe_label(result.get("parent"), field="parent")
    properties = result.get("properties")
    result["properties"] = properties if isinstance(properties, dict) else {}
    if "size" in result["properties"]:
        result["properties"]["size"] = _bounded_float(
            result["properties"].get("size"),
            field="properties.size",
            default=1.0,
            minimum=0.001,
            maximum=10000.0,
        )
    return result


def _validate_move_object(args: Dict[str, Any]) -> Dict[str, Any]:
    result = dict(args)
    result["target"] = _safe_label(result.get("target") or result.get("name"), field="target")
    has_transform = False
    for field in ("position", "rotation", "scale"):
        if result.get(field) is not None:
            result[field] = _vector3(result.get(field), field=field, default=None)
            has_transform = True
    if not has_transform:
        raise McpClientError("Blender object transform requires position, rotation, or scale.")
    return result


def _validate_save_scene(args: Dict[str, Any], *, project_id: str | None) -> Dict[str, Any]:
    result = dict(args)
    scene_path = str(result.get("scene_path") or "").strip()
    if not scene_path:
        if bool(result.get("allow_current_file")):
            result["allow_current_file"] = True
            return result
        raise McpClientError(
            "Blender scene save requires `scene_path`, or explicit `allow_current_file=true`."
        )

    _reject_unsafe_path_text(scene_path)
    if Path(scene_path).suffix.lower() != ".blend":
        raise McpClientError("Blender scene_path must end with `.blend`.")
    result["scene_path"] = _resolve_safe_blend_path(
        scene_path,
        project_id=project_id,
        workspace_id=result.get("workspace_id"),
    )
    return result


def _validate_run_project(args: Dict[str, Any]) -> Dict[str, Any]:
    result = dict(args)
    mode = str(result.get("mode") or "render_still").strip().lower()
    if mode not in BLENDER_RUN_MODES:
        raise McpClientError(
            f"Unsupported Blender run mode `{mode}`. Allowed: {', '.join(sorted(BLENDER_RUN_MODES))}."
        )
    result["mode"] = mode
    result["max_size"] = _bounded_int(result.get("max_size"), default=1000, minimum=256, maximum=2048)
    return result


def _validate_script(args: Dict[str, Any]) -> Dict[str, Any]:
    result = dict(args)
    content = str(result.get("content") or result.get("code") or "").strip()
    if not content:
        raise McpClientError("Blender Python execution requires `content`.")
    if len(content) > 20000:
        raise McpClientError("Blender Python content is too large. Keep it under 20000 characters.")
    for pattern in _FORBIDDEN_PY_PATTERNS:
        if pattern.search(content):
            raise McpClientError(
                "Blender Python contains forbidden system, file, network, or process operations."
            )
    result["content"] = content
    return result


def _resolve_safe_blend_path(
    raw_path: str,
    *,
    project_id: str | None,
    workspace_id: Any,
) -> str:
    if not project_id:
        return str(Path(raw_path).resolve() if Path(raw_path).is_absolute() else Path(raw_path))

    resolved_project = resolve_project_id(project_id)
    if not resolved_project:
        raise McpClientError("Project id is required for safe Blender save path validation.")

    path = Path(raw_path)
    if path.is_absolute():
        target = path.resolve()
        for workspace in _candidate_writable_workspaces(resolved_project):
            root = Path(str(workspace.get("root") or "")).resolve()
            try:
                target.relative_to(root)
            except ValueError:
                continue
            return str(target)
        raise McpClientError(
            "Blender scene_path must be inside an approved writable Blender or Generic workspace."
        )

    try:
        target = resolve_workspace_target(
            resolved_project,
            workspace_id=str(workspace_id or "").strip() or None,
            kind=None if workspace_id else "blender",
            relative_path=raw_path,
            operation="create",
            require_enabled=True,
            require_writable=True,
        )
    except WorkspaceAccessError as exc:
        if workspace_id:
            raise McpClientError(str(exc)) from exc
        try:
            target = resolve_workspace_target(
                resolved_project,
                kind="generic",
                relative_path=raw_path,
                operation="create",
                require_enabled=True,
                require_writable=True,
            )
        except WorkspaceAccessError as fallback_exc:
            raise McpClientError(
                "Blender scene_path must resolve inside an approved writable Blender or Generic workspace."
            ) from fallback_exc
    return str(target.target)


def _candidate_writable_workspaces(project_id: str) -> Iterable[dict]:
    return [
        workspace
        for workspace in list_project_workspaces(project_id, include_disabled=False)
        if workspace.get("enabled", True)
        and workspace.get("writable", False)
        and workspace.get("kind") in {"blender", "generic"}
    ]


def _safe_label(value: Any, *, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise McpClientError(f"Blender `{field}` is required.")
    if len(text) > 120:
        raise McpClientError(f"Blender `{field}` is too long. Keep it under 120 characters.")
    if _CONTROL_CHAR_RE.search(text):
        raise McpClientError(f"Blender `{field}` contains control characters.")
    return text


def _vector3(
    value: Any,
    *,
    field: str,
    default: tuple[float, float, float] | None,
) -> tuple[float, float, float] | None:
    if value is None:
        return default
    if isinstance(value, dict):
        result = (
            _bounded_float(value.get("x"), field=f"{field}.x", default=0.0),
            _bounded_float(value.get("y"), field=f"{field}.y", default=0.0),
            _bounded_float(value.get("z"), field=f"{field}.z", default=0.0),
        )
    elif isinstance(value, (list, tuple)) and len(value) >= 3:
        result = (
            _bounded_float(value[0], field=f"{field}.x", default=0.0),
            _bounded_float(value[1], field=f"{field}.y", default=0.0),
            _bounded_float(value[2], field=f"{field}.z", default=0.0),
        )
    else:
        raise McpClientError(
            f"Blender `{field}` must be a vector object with x/y/z or a 3-item list."
        )
    return result


def _bounded_float(
    value: Any,
    *,
    field: str,
    default: float,
    minimum: float = -100000.0,
    maximum: float = 100000.0,
) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = default
    if not math.isfinite(number) or number < minimum or number > maximum:
        raise McpClientError(
            f"Blender `{field}` must be a finite number between {minimum} and {maximum}."
        )
    return number


def _bounded_int(value: Any, *, default: int, minimum: int, maximum: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default
    if number < minimum or number > maximum:
        raise McpClientError(
            f"Blender integer value must be between {minimum} and {maximum}."
        )
    return number


def _reject_unsafe_path_text(path: str) -> None:
    if _PATH_EXPANSION_RE.match(path):
        raise McpClientError("Blender scene_path cannot use home, environment, or shell expansion.")
    if path.startswith("\\\\"):
        raise McpClientError("Blender scene_path cannot be a UNC path.")
    if _GLOB_RE.search(path):
        raise McpClientError("Blender scene_path cannot contain glob characters.")
