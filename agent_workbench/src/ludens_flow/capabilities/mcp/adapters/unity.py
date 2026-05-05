"""Unity MCP adapter definitions."""

from __future__ import annotations

from typing import Any, Dict

from ludens_flow.capabilities.mcp.adapters.base import BaseEngineAdapter
from ludens_flow.capabilities.mcp.adapters.safe_schema import validate_safe_engine_args


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
        "engine_list_scene": [
            "get_scene_hierarchy",
            "get_current_scene_hierarchy",
            "list_scene",
            "list_gameobjects",
            "get_hierarchy",
        ],
        "engine_create_object": [
            "create_gameobject",
            "create_object",
            "create_prefab",
            "add_gameobject",
        ],
        "engine_move_object": [
            "move_gameobject",
            "set_transform",
            "modify_gameobject",
            "update_transform",
        ],
        "engine_save_scene": ["save_scene", "save_current_scene"],
        "engine_read_console": [
            "read_console",
            "get_console_logs",
            "get_logs",
            "get_log_entries",
        ],
        "engine_run_project": ["start_play_mode", "run_tests", "play_unity_game"],
        "engine_create_script": ["create_script", "create_csharp_script"],
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
