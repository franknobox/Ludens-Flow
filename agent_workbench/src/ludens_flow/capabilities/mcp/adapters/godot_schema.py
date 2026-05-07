"""Godot MCP parameter schemas and safety validation."""

from __future__ import annotations

import math
from pathlib import Path
import re
from typing import Any, Dict

from ludens_flow.capabilities.mcp.health import McpClientError
from ludens_flow.capabilities.workspaces import (
    WorkspaceAccessError,
    WorkspaceBinding,
    resolve_workspace_binding,
)
from ludens_flow.core.paths import resolve_project_id


GODOT_SCENE_EXTENSIONS = frozenset({".tscn", ".scn"})
GODOT_SCRIPT_EXTENSIONS = frozenset({".gd", ".cs"})
GODOT_RUN_MODES = frozenset(
    {
        "run",
        "play",
        "debug",
        "launch_editor",
        "editor",
        "stop",
    }
)

_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
_GODOT_CLASS_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_PATH_EXPANSION_RE = re.compile(r"^(~|%[^%]+%|\$[A-Za-z_][A-Za-z0-9_]*|\$\{.+\})")
_GLOB_RE = re.compile(r"[*?\[\]{}]")


def validate_godot_args(
    capability: str,
    args: Dict[str, Any],
    *,
    project_id: str | None = None,
) -> Dict[str, Any]:
    if not isinstance(args, dict):
        raise McpClientError("Godot tool arguments must be an object.")
    normalized = dict(args)
    engine = str(normalized.get("engine") or "").strip().lower()
    if engine != "godot":
        raise McpClientError("Godot capability requires `engine` to be `godot`.")

    if capability == "engine_list_scene":
        return _validate_list_scene(normalized, project_id=project_id)
    if capability == "engine_read_console":
        return _validate_read_console(normalized)
    if capability == "engine_create_object":
        return _validate_create_object(normalized, project_id=project_id)
    if capability == "engine_move_object":
        return _validate_move_object(normalized, project_id=project_id)
    if capability == "engine_save_scene":
        return _validate_save_scene(normalized, project_id=project_id)
    if capability == "engine_run_project":
        return _validate_run_project(normalized, project_id=project_id)
    if capability == "engine_create_script":
        return _validate_create_script(normalized, project_id=project_id)
    raise McpClientError(f"Unsupported Godot capability schema: {capability}")


def _validate_list_scene(args: Dict[str, Any], *, project_id: str | None) -> Dict[str, Any]:
    result = dict(args)
    binding = _resolve_godot_project_binding(
        project_id=project_id,
        workspace_id=result.get("workspace_id"),
        require_writable=False,
    )
    result["project_path"] = str(binding.root)
    result["max_items"] = _bounded_int(result.get("max_items"), default=200, minimum=1, maximum=1000)
    return result


def _validate_read_console(args: Dict[str, Any]) -> Dict[str, Any]:
    result = dict(args)
    result["max_entries"] = _bounded_int(result.get("max_entries"), default=200, minimum=1, maximum=1000)
    if result.get("filter") is not None:
        result["filter"] = _bounded_text(result.get("filter"), field="filter", max_length=200)
    return result


def _validate_create_object(args: Dict[str, Any], *, project_id: str | None) -> Dict[str, Any]:
    result = dict(args)
    binding = _resolve_godot_project_binding(
        project_id=project_id,
        workspace_id=result.get("workspace_id"),
        require_writable=True,
    )
    properties = result.get("properties") if isinstance(result.get("properties"), dict) else {}
    result["properties"] = dict(properties)
    result["project_path"] = str(binding.root)
    result["scene_path"] = _safe_project_relative_path(
        result.get("scene_path") or properties.get("scene_path"),
        field="scene_path",
        allowed_extensions=GODOT_SCENE_EXTENSIONS,
    )
    result["name"] = _safe_label(result.get("name"), field="name")
    result["object_type"] = _safe_godot_class(
        result.get("object_type") or properties.get("node_type") or "Node2D",
        field="object_type",
    )
    result["root_node_type"] = _safe_godot_class(
        result.get("root_node_type") or properties.get("root_node_type") or result["object_type"],
        field="root_node_type",
    )
    if result.get("parent") is not None:
        result["parent"] = _safe_node_path(result.get("parent"), field="parent")
    elif properties.get("parent_node_path") is not None:
        result["parent"] = _safe_node_path(properties.get("parent_node_path"), field="parent")
    else:
        result["parent"] = "root"
    for field in ("position", "rotation", "scale"):
        value = result.get(field, properties.get(field))
        if value is not None:
            result[field] = _vector(value, field=field)
    result["create_scene"] = bool(result.get("create_scene") or properties.get("create_scene"))
    result.pop("workspace_id", None)
    return result


def _validate_move_object(args: Dict[str, Any], *, project_id: str | None) -> Dict[str, Any]:
    result = dict(args)
    binding = _resolve_godot_project_binding(
        project_id=project_id,
        workspace_id=result.get("workspace_id"),
        require_writable=True,
    )
    properties = result.get("properties") if isinstance(result.get("properties"), dict) else {}
    result["project_path"] = str(binding.root)
    result["scene_path"] = _safe_project_relative_path(
        result.get("scene_path") or properties.get("scene_path"),
        field="scene_path",
        allowed_extensions=GODOT_SCENE_EXTENSIONS,
    )
    result["target"] = _safe_node_path(result.get("target") or result.get("name"), field="target")
    if not any(result.get(field) is not None for field in ("position", "rotation", "scale")):
        raise McpClientError("Godot object update requires position, rotation, or scale.")
    for field in ("position", "rotation", "scale"):
        if result.get(field) is not None:
            result[field] = _vector(result.get(field), field=field)
    result.pop("workspace_id", None)
    return result


def _validate_save_scene(args: Dict[str, Any], *, project_id: str | None) -> Dict[str, Any]:
    result = dict(args)
    binding = _resolve_godot_project_binding(
        project_id=project_id,
        workspace_id=result.get("workspace_id"),
        require_writable=True,
    )
    result["project_path"] = str(binding.root)
    result["scene_path"] = _safe_project_relative_path(
        result.get("scene_path"),
        field="scene_path",
        allowed_extensions=GODOT_SCENE_EXTENSIONS,
    )
    if result.get("new_path") is not None:
        result["new_path"] = _safe_project_relative_path(
            result.get("new_path"),
            field="new_path",
            allowed_extensions=GODOT_SCENE_EXTENSIONS,
        )
    result.pop("workspace_id", None)
    return result


def _validate_run_project(args: Dict[str, Any], *, project_id: str | None) -> Dict[str, Any]:
    result = dict(args)
    binding = _resolve_godot_project_binding(
        project_id=project_id,
        workspace_id=result.get("workspace_id"),
        require_writable=False,
    )
    mode = str(result.get("mode") or "run").strip().lower()
    if mode not in GODOT_RUN_MODES:
        raise McpClientError(
            f"Unsupported Godot run mode `{mode}`. Allowed: {', '.join(sorted(GODOT_RUN_MODES))}."
        )
    result["mode"] = mode
    result["project_path"] = str(binding.root)
    scene_path = str(result.get("scene_path") or "").strip()
    if scene_path:
        result["scene_path"] = _safe_project_relative_path(
            scene_path,
            field="scene_path",
            allowed_extensions=GODOT_SCENE_EXTENSIONS,
        )
    else:
        result.pop("scene_path", None)
    result.pop("workspace_id", None)
    return result


def _validate_create_script(args: Dict[str, Any], *, project_id: str | None) -> Dict[str, Any]:
    result = dict(args)
    binding = _resolve_godot_project_binding(
        project_id=project_id,
        workspace_id=result.get("workspace_id"),
        require_writable=True,
    )
    path = str(result.get("path") or "").strip()
    if not path and result.get("class_name") is not None:
        path = f"scripts/{_safe_label(result.get('class_name'), field='class_name')}.gd"
    if not path:
        raise McpClientError("Godot script creation requires `path`.")
    result["project_path"] = str(binding.root)
    result["path"] = _safe_project_relative_path(
        path,
        field="path",
        allowed_extensions=GODOT_SCRIPT_EXTENSIONS,
    )
    content = str(result.get("content") or result.get("contents") or "")
    if len(content) > 50000:
        raise McpClientError("Godot script content is too large. Keep it under 50000 characters.")
    if _CONTROL_CHAR_RE.search(content):
        raise McpClientError("Godot script content contains control characters.")
    result["content"] = content
    result.pop("workspace_id", None)
    return result


def _resolve_godot_project_binding(
    *,
    project_id: str | None,
    workspace_id: Any,
    require_writable: bool,
) -> WorkspaceBinding:
    if not project_id:
        raise McpClientError("Project id is required for safe Godot project validation.")
    resolved_project = resolve_project_id(project_id)
    if not resolved_project:
        raise McpClientError("Project id could not be resolved for Godot validation.")
    requested_workspace_id = str(workspace_id or "").strip() or None
    attempts = [None] if requested_workspace_id else ["godot", "generic"]
    last_error: Exception | None = None
    for kind in attempts:
        try:
            binding = resolve_workspace_binding(
                resolved_project,
                workspace_id=requested_workspace_id,
                kind=kind,
                require_enabled=True,
                require_writable=require_writable,
            )
            _ensure_godot_project_root(binding.root)
            return binding
        except (WorkspaceAccessError, McpClientError) as exc:
            last_error = exc
    raise McpClientError(str(last_error) if last_error else "No Godot workspace is configured.")


def _ensure_godot_project_root(root: Path) -> None:
    project_file = root / "project.godot"
    if not project_file.exists() or not project_file.is_file():
        raise McpClientError(f"Godot workspace must point to a project directory containing project.godot: {root}")


def _safe_project_relative_path(
    value: Any,
    *,
    field: str,
    allowed_extensions: frozenset[str],
) -> str:
    raw = str(value or "").strip()
    if raw.startswith("res://"):
        raw = raw.removeprefix("res://")
    raw = raw.strip().strip("/").replace("\\", "/")
    if not raw:
        raise McpClientError(f"Godot `{field}` is required.")
    if _PATH_EXPANSION_RE.match(raw):
        raise McpClientError(f"Godot `{field}` cannot use home, environment, or shell expansion.")
    if raw.startswith("\\\\") or Path(raw).is_absolute() or re.match(r"^[A-Za-z]:[\\/]", raw):
        raise McpClientError(f"Godot `{field}` must be relative to the approved Godot workspace.")
    if any(part == ".." for part in raw.split("/")):
        raise McpClientError(f"[WORKSPACE_ACCESS_ERROR:PATH_ESCAPE] Godot `{field}` cannot escape the project root.")
    if _GLOB_RE.search(raw):
        raise McpClientError(f"Godot `{field}` cannot contain glob characters.")
    suffix = Path(raw).suffix.lower()
    if suffix not in allowed_extensions:
        raise McpClientError(
            f"Godot `{field}` must use one of these extensions: {', '.join(sorted(allowed_extensions))}."
        )
    return raw


def _safe_godot_class(value: Any, *, field: str) -> str:
    text = _safe_label(value, field=field)
    if not _GODOT_CLASS_RE.match(text):
        raise McpClientError(f"Godot `{field}` must be a Godot class name, not a path.")
    return text


def _safe_node_path(value: Any, *, field: str) -> str:
    text = _bounded_text(value, field=field, max_length=200)
    if not text:
        raise McpClientError(f"Godot `{field}` is required.")
    if _CONTROL_CHAR_RE.search(text) or ".." in text:
        raise McpClientError(f"Godot `{field}` is invalid.")
    return text


def _safe_label(value: Any, *, field: str) -> str:
    text = _bounded_text(value, field=field, max_length=120)
    if not text:
        raise McpClientError(f"Godot `{field}` is required.")
    return text


def _bounded_text(value: Any, *, field: str, max_length: int) -> str:
    text = str(value or "").strip()
    if len(text) > max_length:
        raise McpClientError(f"Godot `{field}` is too long. Keep it under {max_length} characters.")
    if _CONTROL_CHAR_RE.search(text):
        raise McpClientError(f"Godot `{field}` contains control characters.")
    return text


def _vector(value: Any, *, field: str) -> list[float]:
    if isinstance(value, dict):
        raw = [value.get("x"), value.get("y")]
        if value.get("z") is not None:
            raw.append(value.get("z"))
    elif isinstance(value, (list, tuple)) and len(value) >= 2:
        raw = list(value[:3])
    else:
        raise McpClientError(f"Godot `{field}` must be a vector object with x/y or x/y/z, or a 2/3-item list.")
    result = [_bounded_float(item, field=field) for item in raw]
    return result


def _bounded_float(value: Any, *, field: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = 0.0
    if not math.isfinite(number) or number < -100000.0 or number > 100000.0:
        raise McpClientError(f"Godot `{field}` must be a finite number between -100000 and 100000.")
    return number


def _bounded_int(value: Any, *, default: int, minimum: int, maximum: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default
    if number < minimum or number > maximum:
        raise McpClientError(f"Godot integer value must be between {minimum} and {maximum}.")
    return number
