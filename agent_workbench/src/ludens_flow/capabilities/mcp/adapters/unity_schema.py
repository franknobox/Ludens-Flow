"""Unity MCP parameter schemas and safety validation."""

from __future__ import annotations

import math
from pathlib import Path
import re
from typing import Any, Dict

from ludens_flow.capabilities.mcp.health import McpClientError
from ludens_flow.capabilities.workspaces import WorkspaceAccessError, resolve_workspace_target
from ludens_flow.core.paths import resolve_project_id


UNITY_PRIMITIVE_TYPES = frozenset(
    {
        "cube",
        "sphere",
        "capsule",
        "cylinder",
        "plane",
        "quad",
    }
)
UNITY_RUN_MODES = frozenset(
    {
        "play",
        "play_mode",
        "stop",
        "pause",
        "test",
        "tests",
        "editmode_tests",
        "playmode_tests",
    }
)

_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
_CS_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_PATH_EXPANSION_RE = re.compile(r"^(~|%[^%]+%|\$[A-Za-z_][A-Za-z0-9_]*|\$\{.+\})")
_GLOB_RE = re.compile(r"[*?\[\]{}]")


def validate_unity_args(
    capability: str,
    args: Dict[str, Any],
    *,
    project_id: str | None = None,
) -> Dict[str, Any]:
    if not isinstance(args, dict):
        raise McpClientError("Unity tool arguments must be an object.")
    normalized = dict(args)
    engine = str(normalized.get("engine") or "").strip().lower()
    if engine != "unity":
        raise McpClientError("Unity capability requires `engine` to be `unity`.")

    if capability == "engine_list_scene":
        normalized["max_items"] = _bounded_int(normalized.get("max_items"), default=200, minimum=1, maximum=1000)
        return normalized
    if capability == "engine_read_console":
        return _validate_read_console(normalized)
    if capability == "engine_create_script":
        return _validate_create_script(normalized, project_id=project_id)
    if capability == "engine_create_object":
        return _validate_create_object(normalized, project_id=project_id)
    if capability == "engine_move_object":
        return _validate_move_object(normalized)
    if capability == "engine_save_scene":
        return _validate_save_scene(normalized, project_id=project_id)
    if capability == "engine_run_project":
        return _validate_run_project(normalized)
    raise McpClientError(f"Unsupported Unity capability schema: {capability}")


def _validate_read_console(args: Dict[str, Any]) -> Dict[str, Any]:
    result = dict(args)
    result["max_entries"] = _bounded_int(result.get("max_entries"), default=50, minimum=1, maximum=500)
    if result.get("filter") is not None:
        result["filter"] = _bounded_text(result.get("filter"), field="filter", max_length=200)
    return result


def _validate_create_script(args: Dict[str, Any], *, project_id: str | None) -> Dict[str, Any]:
    result = dict(args)
    path = str(result.get("path") or "").strip()
    class_name = str(result.get("class_name") or "").strip()
    if not path:
        if not class_name:
            raise McpClientError("Unity script creation requires `path` or `class_name`.")
        class_name = _safe_identifier(class_name, field="class_name")
        path = f"Assets/Scripts/{class_name}.cs"

    assets_path = _resolve_assets_relative_path(
        path,
        project_id=project_id,
        workspace_id=result.get("workspace_id"),
        allowed_suffix=".cs",
        field="path",
        require_writable=True,
    )
    result["path"] = assets_path
    result.pop("workspace_id", None)

    if class_name:
        result["class_name"] = _safe_identifier(class_name, field="class_name")
    content = str(result.get("content") or result.get("contents") or "")
    if len(content) > 50000:
        raise McpClientError("Unity script content is too large. Keep it under 50000 characters.")
    if _CONTROL_CHAR_RE.search(content):
        raise McpClientError("Unity script content contains control characters.")
    result["content"] = content
    return result


def _validate_create_object(args: Dict[str, Any], *, project_id: str | None) -> Dict[str, Any]:
    result = dict(args)
    result["name"] = _safe_label(result.get("name"), field="name")
    properties = result.get("properties") if isinstance(result.get("properties"), dict) else {}
    result["properties"] = properties

    object_type = str(result.get("object_type") or properties.get("object_type") or "empty").strip().lower()
    prefab_path = str(properties.get("prefab_path") or properties.get("prefabPath") or "").strip()
    if not prefab_path and object_type.endswith(".prefab"):
        prefab_path = object_type
        object_type = "prefab"
    if prefab_path:
        result["prefab_path"] = _validate_unity_asset_path(
            prefab_path,
            suffix=".prefab",
            field="prefab_path",
            project_id=project_id,
            workspace_id=result.get("workspace_id"),
            require_existing_workspace=False,
        )
        object_type = "prefab"

    if object_type != "prefab" and object_type not in UNITY_PRIMITIVE_TYPES and object_type != "empty":
        raise McpClientError(
            f"Unsupported Unity object_type `{object_type}`. Allowed: empty, prefab, {', '.join(sorted(UNITY_PRIMITIVE_TYPES))}."
        )
    result["object_type"] = object_type

    for field in ("position", "rotation", "scale"):
        if result.get(field) is not None:
            result[field] = _vector3(result.get(field), field=field)
        elif properties.get(field) is not None:
            result[field] = _vector3(properties.get(field), field=field)
    if result.get("parent") is not None:
        result["parent"] = _safe_label(result.get("parent"), field="parent")
    for field in ("tag", "layer"):
        value = result.get(field, properties.get(field))
        if value is not None:
            result[field] = _safe_label(value, field=field)
    for field in ("components_to_add", "components_to_remove"):
        value = result.get(field, properties.get(field))
        if value is not None:
            result[field] = _string_list(value, field=field)
    return result


def _validate_move_object(args: Dict[str, Any]) -> Dict[str, Any]:
    result = dict(args)
    result["target"] = _safe_label(result.get("target") or result.get("name"), field="target")
    properties = result.get("properties") if isinstance(result.get("properties"), dict) else {}
    has_transform = False
    for field in ("position", "rotation", "scale"):
        value = result.get(field, properties.get(field))
        if value is not None:
            result[field] = _vector3(value, field=field)
            has_transform = True
    for field in ("parent", "new_name", "tag", "layer"):
        value = result.get(field, properties.get(field))
        if value is not None:
            result[field] = _safe_label(value, field=field)
    if properties.get("set_active") is not None:
        result["set_active"] = bool(properties.get("set_active"))
    if properties.get("components_to_add") is not None:
        result["components_to_add"] = _string_list(properties.get("components_to_add"), field="components_to_add")
    if properties.get("components_to_remove") is not None:
        result["components_to_remove"] = _string_list(properties.get("components_to_remove"), field="components_to_remove")
    if properties.get("component_properties") is not None:
        component_properties = properties.get("component_properties")
        if not isinstance(component_properties, dict):
            raise McpClientError("Unity `component_properties` must be an object.")
        result["component_properties"] = component_properties
    if not has_transform and not any(key in result for key in ("parent", "new_name", "tag", "layer", "set_active", "components_to_add", "components_to_remove", "component_properties")):
        raise McpClientError("Unity object update requires position, rotation, scale, parent, tag, layer, active state, component updates, or new_name.")
    return result


def _validate_save_scene(args: Dict[str, Any], *, project_id: str | None) -> Dict[str, Any]:
    result = dict(args)
    scene_path = str(result.get("scene_path") or "").strip()
    if not scene_path:
        result["scene_path"] = ""
        return result
    result["scene_path"] = _resolve_assets_relative_path(
        scene_path,
        project_id=project_id,
        workspace_id=result.get("workspace_id"),
        allowed_suffix=".unity",
        field="scene_path",
        require_writable=True,
    )
    result.pop("workspace_id", None)
    return result


def _validate_run_project(args: Dict[str, Any]) -> Dict[str, Any]:
    result = dict(args)
    mode = str(result.get("mode") or "play").strip().lower()
    if mode not in UNITY_RUN_MODES:
        raise McpClientError(
            f"Unsupported Unity run mode `{mode}`. Allowed: {', '.join(sorted(UNITY_RUN_MODES))}."
        )
    result["mode"] = mode
    return result


def _resolve_assets_relative_path(
    raw_path: str,
    *,
    project_id: str | None,
    workspace_id: Any,
    allowed_suffix: str,
    field: str,
    require_writable: bool,
) -> str:
    _reject_unsafe_path_text(raw_path, field=field)
    if not project_id:
        raise McpClientError(f"Project id is required for safe Unity `{field}` validation.")

    relative_path = _normalize_assets_path(raw_path)
    if Path(relative_path).suffix.lower() != allowed_suffix:
        raise McpClientError(f"Unity `{field}` must use `{allowed_suffix}`.")

    try:
        target = resolve_workspace_target(
            resolve_project_id(project_id),
            workspace_id=str(workspace_id or "").strip() or None,
            kind=None if workspace_id else "unity",
            relative_path=relative_path,
            operation="create",
            require_enabled=True,
            require_writable=require_writable,
        )
    except WorkspaceAccessError as exc:
        raise McpClientError(str(exc)) from exc

    return _assets_relative_from_target(target.target, target.binding.root)


def _validate_unity_asset_path(
    raw_path: str,
    *,
    suffix: str,
    field: str,
    project_id: str | None,
    workspace_id: Any,
    require_existing_workspace: bool,
) -> str:
    _reject_unsafe_path_text(raw_path, field=field)
    text = raw_path.replace("\\", "/").strip()
    if "/" not in text:
        return text
    if Path(text).suffix.lower() != suffix:
        raise McpClientError(f"Unity `{field}` must use `{suffix}`.")
    if not text.lower().startswith("assets/"):
        raise McpClientError(f"Unity `{field}` must be an Assets-relative path or a simple asset name.")
    if require_existing_workspace:
        return _resolve_assets_relative_path(
            text,
            project_id=project_id,
            workspace_id=workspace_id,
            allowed_suffix=suffix,
            field=field,
            require_writable=False,
        )
    return text


def _normalize_assets_path(raw_path: str) -> str:
    normalized = raw_path.replace("\\", "/").strip().strip("/")
    if not normalized.lower().startswith("assets/"):
        normalized = f"Assets/{normalized}"
    return normalized


def _assets_relative_from_target(target: Path, root: Path) -> str:
    relative = target.resolve().relative_to(root.resolve()).as_posix()
    if not relative.lower().startswith("assets/"):
        raise McpClientError("Unity paths must stay inside the project's Assets directory.")
    return relative


def _safe_identifier(value: Any, *, field: str) -> str:
    text = _safe_label(value, field=field)
    if not _CS_IDENTIFIER_RE.match(text):
        raise McpClientError(f"Unity `{field}` must be a valid C# identifier.")
    return text


def _safe_label(value: Any, *, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise McpClientError(f"Unity `{field}` is required.")
    if len(text) > 120:
        raise McpClientError(f"Unity `{field}` is too long. Keep it under 120 characters.")
    if _CONTROL_CHAR_RE.search(text):
        raise McpClientError(f"Unity `{field}` contains control characters.")
    return text


def _bounded_text(value: Any, *, field: str, max_length: int) -> str:
    text = str(value or "").strip()
    if len(text) > max_length:
        raise McpClientError(f"Unity `{field}` is too long. Keep it under {max_length} characters.")
    if _CONTROL_CHAR_RE.search(text):
        raise McpClientError(f"Unity `{field}` contains control characters.")
    return text


def _vector3(value: Any, *, field: str) -> list[float]:
    if isinstance(value, dict):
        result = [
            _bounded_float(value.get("x"), field=f"{field}.x"),
            _bounded_float(value.get("y"), field=f"{field}.y"),
            _bounded_float(value.get("z"), field=f"{field}.z"),
        ]
    elif isinstance(value, (list, tuple)) and len(value) >= 3:
        result = [
            _bounded_float(value[0], field=f"{field}.x"),
            _bounded_float(value[1], field=f"{field}.y"),
            _bounded_float(value[2], field=f"{field}.z"),
        ]
    else:
        raise McpClientError(f"Unity `{field}` must be a vector object with x/y/z or a 3-item list.")
    return result


def _bounded_float(value: Any, *, field: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = 0.0
    if not math.isfinite(number) or number < -100000.0 or number > 100000.0:
        raise McpClientError(f"Unity `{field}` must be a finite number between -100000 and 100000.")
    return number


def _bounded_int(value: Any, *, default: int, minimum: int, maximum: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default
    if number < minimum or number > maximum:
        raise McpClientError(f"Unity integer value must be between {minimum} and {maximum}.")
    return number


def _string_list(value: Any, *, field: str) -> list[str]:
    if isinstance(value, str):
        items = [value]
    elif isinstance(value, (list, tuple)):
        items = [str(item).strip() for item in value if str(item).strip()]
    else:
        raise McpClientError(f"Unity `{field}` must be a string or string list.")
    if not items:
        raise McpClientError(f"Unity `{field}` cannot be empty.")
    return [_safe_label(item, field=field) for item in items]


def _reject_unsafe_path_text(path: str, *, field: str) -> None:
    raw = str(path or "").strip()
    normalized = raw.replace("\\", "/")
    if _PATH_EXPANSION_RE.match(raw):
        raise McpClientError(f"Unity `{field}` cannot use home, environment, or shell expansion.")
    if raw.startswith("\\\\"):
        raise McpClientError(f"Unity `{field}` cannot be a UNC path.")
    if Path(raw).is_absolute() or re.match(r"^[A-Za-z]:[\\/]", raw):
        raise McpClientError(f"Unity `{field}` must be relative to the approved Unity workspace.")
    if any(part == ".." for part in normalized.split("/")):
        raise McpClientError(f"[WORKSPACE_ACCESS_ERROR:PATH_ESCAPE] Unity `{field}` cannot escape the Assets directory.")
    if _GLOB_RE.search(raw):
        raise McpClientError(f"Unity `{field}` cannot contain glob characters.")
