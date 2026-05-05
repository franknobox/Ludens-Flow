"""Shared MCP adapter validation for engines without bespoke schemas."""

from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any, Dict, Iterable

from ludens_flow.capabilities.mcp.health import McpClientError
from ludens_flow.capabilities.workspaces import WorkspaceAccessError, resolve_workspace_target
from ludens_flow.core.paths import resolve_project_id


_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
_SCRIPT_EXTENSIONS = {
    "unity": frozenset({".cs"}),
    "godot": frozenset({".gd", ".cs"}),
    "unreal": frozenset({".cpp", ".h", ".hpp"}),
}
_SCENE_EXTENSIONS = {
    "unity": frozenset({".unity"}),
    "godot": frozenset({".tscn", ".scn"}),
    "unreal": frozenset({".umap"}),
}
_RUN_MODES = {
    "unity": frozenset({"play", "play_mode", "test", "tests"}),
    "godot": frozenset({"run", "play", "debug"}),
    "unreal": frozenset({"play", "pie", "simulate"}),
}


def validate_safe_engine_args(
    engine: str,
    capability: str,
    args: Dict[str, Any],
    *,
    project_id: str | None,
) -> Dict[str, Any]:
    if not isinstance(args, dict):
        raise McpClientError(f"{engine.title()} tool arguments must be an object.")

    normalized: Dict[str, Any] = {
        key: value
        for key, value in args.items()
        if key not in {"engine", "connection_id"} and value is not None
    }
    requested_engine = str(args.get("engine") or "").strip().lower()
    if requested_engine != engine:
        raise McpClientError(f"{engine.title()} capability requires `engine` to be `{engine}`.")

    if capability == "engine_list_scene":
        return _validate_list_scene(engine, normalized)
    if capability == "engine_create_object":
        return _validate_create_object(engine, normalized)
    if capability == "engine_move_object":
        return _validate_move_object(engine, normalized)
    if capability == "engine_save_scene":
        return _validate_save_scene(engine, normalized, project_id=project_id)
    if capability == "engine_read_console":
        return _validate_read_console(engine, normalized)
    if capability == "engine_run_project":
        return _validate_run_project(engine, normalized, project_id=project_id)
    if capability == "engine_create_script":
        return _validate_create_script(engine, normalized, project_id=project_id)
    return normalized


def _validate_list_scene(engine: str, args: Dict[str, Any]) -> Dict[str, Any]:
    result = dict(args)
    if "scene_path" in result and str(result.get("scene_path") or "").strip():
        result["scene_path"] = _safe_relative_path(
            engine,
            str(result.get("scene_path") or ""),
            field="scene_path",
            allowed_extensions=_SCENE_EXTENSIONS.get(engine, frozenset()),
        )
    result["max_items"] = _bounded_int(result.get("max_items"), default=200, minimum=1, maximum=1000)
    return result


def _validate_create_object(engine: str, args: Dict[str, Any]) -> Dict[str, Any]:
    result = dict(args)
    result["name"] = _safe_label(engine, result.get("name"), field="name")
    if result.get("object_type") is not None:
        result["object_type"] = _safe_label(engine, result.get("object_type"), field="object_type")
    if result.get("parent") is not None:
        result["parent"] = _safe_label(engine, result.get("parent"), field="parent")
    for field in ("position", "rotation", "scale"):
        if result.get(field) is not None:
            result[field] = _vector3(engine, result.get(field), field=field)
    if result.get("properties") is not None and not isinstance(result.get("properties"), dict):
        raise McpClientError(f"{engine.title()} `properties` must be an object.")
    return result


def _validate_move_object(engine: str, args: Dict[str, Any]) -> Dict[str, Any]:
    result = dict(args)
    result["target"] = _safe_label(engine, result.get("target") or result.get("name"), field="target")
    has_transform = False
    for field in ("position", "rotation", "scale"):
        if result.get(field) is not None:
            result[field] = _vector3(engine, result.get(field), field=field)
            has_transform = True
    if not has_transform:
        raise McpClientError(f"{engine.title()} transform requires position, rotation, or scale.")
    return result


def _validate_save_scene(engine: str, args: Dict[str, Any], *, project_id: str | None) -> Dict[str, Any]:
    result = dict(args)
    scene_path = str(result.get("scene_path") or "").strip()
    if not scene_path:
        raise McpClientError(f"{engine.title()} scene save requires `scene_path`.")
    result["scene_path"] = _resolve_safe_workspace_path(
        engine,
        scene_path,
        workspace_id=result.get("workspace_id"),
        project_id=project_id,
        allowed_extensions=_SCENE_EXTENSIONS.get(engine, frozenset()),
        field="scene_path",
    )
    result.pop("workspace_id", None)
    return result


def _validate_read_console(engine: str, args: Dict[str, Any]) -> Dict[str, Any]:
    result = dict(args)
    result["max_entries"] = _bounded_int(result.get("max_entries"), default=200, minimum=1, maximum=1000)
    if result.get("filter") is not None:
        result["filter"] = _bounded_text(engine, result.get("filter"), field="filter", max_length=200)
    return result


def _validate_run_project(engine: str, args: Dict[str, Any], *, project_id: str | None) -> Dict[str, Any]:
    result = dict(args)
    mode = str(result.get("mode") or _default_run_mode(engine)).strip().lower()
    allowed_modes = _RUN_MODES.get(engine, frozenset())
    if allowed_modes and mode not in allowed_modes:
        raise McpClientError(
            f"Unsupported {engine.title()} run mode `{mode}`. Allowed: {', '.join(sorted(allowed_modes))}."
        )
    result["mode"] = mode
    for field in ("project_path", "scene_path"):
        value = str(result.get(field) or "").strip()
        if not value:
            result.pop(field, None)
            continue
        result[field] = _resolve_safe_workspace_path(
            engine,
            value,
            workspace_id=result.get("workspace_id"),
            project_id=project_id,
            allowed_extensions=_SCENE_EXTENSIONS.get(engine, frozenset()) if field == "scene_path" else None,
            field=field,
            allow_empty=True,
        )
    result.pop("workspace_id", None)
    if result.get("max_size") is not None:
        result["max_size"] = _bounded_int(result.get("max_size"), default=1000, minimum=256, maximum=2048)
    return result


def _validate_create_script(engine: str, args: Dict[str, Any], *, project_id: str | None) -> Dict[str, Any]:
    result = dict(args)
    path = str(result.get("path") or "").strip()
    if not path and result.get("class_name") is not None:
        class_name = _safe_label(engine, result.get("class_name"), field="class_name")
        extension = ".gd" if engine == "godot" else ".cs" if engine == "unity" else ".cpp"
        path = f"{class_name}{extension}"
    if not path:
        raise McpClientError(f"{engine.title()} script creation requires `path`.")
    result["path"] = _resolve_safe_workspace_path(
        engine,
        path,
        workspace_id=result.get("workspace_id"),
        project_id=project_id,
        allowed_extensions=_SCRIPT_EXTENSIONS.get(engine, frozenset()),
        field="path",
    )
    result.pop("workspace_id", None)
    if result.get("class_name") is not None:
        result["class_name"] = _safe_label(engine, result.get("class_name"), field="class_name")
    if result.get("language") is not None:
        result["language"] = _safe_label(engine, result.get("language"), field="language")
    content = str(result.get("content") or "")
    if len(content) > 50000:
        raise McpClientError(f"{engine.title()} script content is too large. Keep it under 50000 characters.")
    if _CONTROL_CHAR_RE.search(content):
        raise McpClientError(f"{engine.title()} script content contains control characters.")
    result["content"] = content
    return result


def _resolve_safe_workspace_path(
    engine: str,
    raw_path: str,
    *,
    workspace_id: Any,
    project_id: str | None,
    allowed_extensions: Iterable[str] | None,
    field: str,
    allow_empty: bool = False,
) -> str:
    if not project_id:
        raise McpClientError(f"Project id is required for safe {engine.title()} `{field}` validation.")
    _validate_extension(engine, raw_path, field=field, allowed_extensions=allowed_extensions)
    resolved_project = resolve_project_id(project_id)
    try:
        target = resolve_workspace_target(
            resolved_project,
            workspace_id=str(workspace_id or "").strip() or None,
            kind=None if workspace_id else _workspace_kind_for_engine(engine),
            relative_path=raw_path,
            operation="create",
            require_enabled=True,
            require_writable=True,
            allow_empty=allow_empty,
        )
    except WorkspaceAccessError as exc:
        raise McpClientError(str(exc)) from exc
    return str(target.target)


def _safe_relative_path(
    engine: str,
    raw_path: str,
    *,
    field: str,
    allowed_extensions: Iterable[str] | None,
) -> str:
    _validate_extension(engine, raw_path, field=field, allowed_extensions=allowed_extensions)
    path = Path(raw_path)
    if path.is_absolute() or str(raw_path).startswith("\\\\"):
        raise McpClientError(f"{engine.title()} `{field}` must be a relative workspace path.")
    if any(part == ".." for part in Path(str(raw_path).replace("\\", "/")).parts):
        raise McpClientError(f"{engine.title()} `{field}` cannot escape the workspace.")
    return str(raw_path).replace("\\", "/")


def _workspace_kind_for_engine(engine: str) -> str:
    if engine == "unity":
        return "unity"
    return "generic"


def _default_run_mode(engine: str) -> str:
    if engine == "unreal":
        return "pie"
    if engine == "godot":
        return "run"
    return "play"


def _validate_extension(
    engine: str,
    path: str,
    *,
    field: str,
    allowed_extensions: Iterable[str] | None,
) -> None:
    allowed = frozenset(str(item).lower() for item in (allowed_extensions or []) if str(item).strip())
    if not allowed:
        return
    suffix = Path(path).suffix.lower()
    if suffix not in allowed:
        raise McpClientError(
            f"{engine.title()} `{field}` must use one of these extensions: {', '.join(sorted(allowed))}."
        )


def _safe_label(engine: str, value: Any, *, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise McpClientError(f"{engine.title()} `{field}` is required.")
    return _bounded_text(engine, text, field=field, max_length=120)


def _bounded_text(engine: str, value: Any, *, field: str, max_length: int) -> str:
    text = str(value or "").strip()
    if len(text) > max_length:
        raise McpClientError(f"{engine.title()} `{field}` is too long. Keep it under {max_length} characters.")
    if _CONTROL_CHAR_RE.search(text):
        raise McpClientError(f"{engine.title()} `{field}` contains control characters.")
    return text


def _vector3(engine: str, value: Any, *, field: str) -> tuple[float, float, float]:
    if isinstance(value, dict):
        result = (
            _bounded_float(engine, value.get("x"), field=f"{field}.x"),
            _bounded_float(engine, value.get("y"), field=f"{field}.y"),
            _bounded_float(engine, value.get("z"), field=f"{field}.z"),
        )
    elif isinstance(value, (list, tuple)) and len(value) >= 3:
        result = (
            _bounded_float(engine, value[0], field=f"{field}.x"),
            _bounded_float(engine, value[1], field=f"{field}.y"),
            _bounded_float(engine, value[2], field=f"{field}.z"),
        )
    else:
        raise McpClientError(f"{engine.title()} `{field}` must be a vector object with x/y/z or a 3-item list.")
    return result


def _bounded_float(engine: str, value: Any, *, field: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = 0.0
    if not math.isfinite(number) or number < -100000.0 or number > 100000.0:
        raise McpClientError(f"{engine.title()} `{field}` must be a finite number between -100000 and 100000.")
    return number


def _bounded_int(value: Any, *, default: int, minimum: int, maximum: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default
    if number < minimum or number > maximum:
        raise McpClientError(f"Integer value must be between {minimum} and {maximum}.")
    return number
