"""Unreal MCP adapter definitions."""

from __future__ import annotations

from typing import Any, Dict

from ludens_flow.capabilities.mcp.adapters.base import BaseEngineAdapter
from ludens_flow.capabilities.mcp.adapters.safe_schema import validate_safe_engine_args


class UnrealEngineAdapter(BaseEngineAdapter):
    engine = "unreal"
    operation_names = {
        "engine_list_scene": "unreal.level.inspect",
        "engine_create_object": "unreal.actor.spawn",
        "engine_move_object": "unreal.actor.transform",
        "engine_save_scene": "unreal.level.save",
        "engine_read_console": "unreal.output_log.read",
        "engine_run_project": "unreal.pie.run",
        "engine_create_script": "unreal.asset.create",
    }
    tool_candidates = {
        "engine_list_scene": ["list_actors", "get_scene_hierarchy", "get_level_actors"],
        "engine_create_object": ["spawn_actor", "create_actor"],
        "engine_move_object": ["set_actor_transform", "move_actor"],
        "engine_save_scene": ["save_level", "save_scene"],
        "engine_read_console": ["get_output_log", "read_console"],
        "engine_run_project": ["play_in_editor", "run_project"],
        "engine_create_script": ["create_blueprint", "create_cpp_class"],
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
        return validate_safe_engine_args(self.engine, capability, args, project_id=project_id)
