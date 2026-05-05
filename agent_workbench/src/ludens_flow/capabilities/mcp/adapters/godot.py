"""Godot MCP adapter definitions."""

from __future__ import annotations

from typing import Any, Dict

from ludens_flow.capabilities.mcp.adapters.base import BaseEngineAdapter
from ludens_flow.capabilities.mcp.adapters.safe_schema import validate_safe_engine_args


class GodotEngineAdapter(BaseEngineAdapter):
    engine = "godot"
    operation_names = {
        "engine_list_scene": "godot.scene_tree.inspect",
        "engine_create_object": "godot.node.create",
        "engine_move_object": "godot.node.transform",
        "engine_save_scene": "godot.scene.save",
        "engine_read_console": "godot.output.read",
        "engine_run_project": "godot.project.run",
        "engine_create_script": "godot.script.create",
    }
    tool_candidates = {
        "engine_list_scene": ["get_project_info", "get_scene_tree", "list_scenes"],
        "engine_create_object": ["add_node", "create_scene"],
        "engine_move_object": ["set_node_properties", "update_node", "move_node"],
        "engine_save_scene": ["save_scene"],
        "engine_read_console": ["get_debug_output"],
        "engine_run_project": ["run_project", "launch_editor"],
        "engine_create_script": ["create_script", "create_gdscript"],
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
