import unittest

from ludens_flow.capabilities.mcp.adapters.unreal import UnrealEngineAdapter
from ludens_flow.capabilities.mcp.health import McpClientError


class UnrealMcpAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.adapter = UnrealEngineAdapter()
        self.tools = [
            {"name": "get_actors_in_level"},
            {"name": "find_actors_by_name"},
            {"name": "get_actor_properties"},
            {"name": "spawn_actor"},
            {"name": "spawn_blueprint_actor"},
            {"name": "set_actor_transform"},
            {"name": "set_actor_property"},
            {"name": "create_blueprint"},
            {"name": "compile_blueprint"},
            {"name": "add_component_to_blueprint"},
            {"name": "set_blueprint_property"},
            {"name": "create_input_mapping"},
            {"name": "save_level"},
            {"name": "read_output_log"},
            {"name": "run_pie"},
        ]

    def test_list_scene_maps_to_actor_list_tool(self) -> None:
        call = self.adapter.map_call("engine_list_scene", {"engine": "unreal"}, self.tools)

        self.assertIsNotNone(call)
        self.assertEqual(call.tool_name, "get_actors_in_level")
        self.assertEqual(call.arguments, {})
        self.assertEqual(call.operation_name, "unreal.level.actors")

    def test_list_scene_can_query_single_actor_properties(self) -> None:
        call = self.adapter.map_call(
            "engine_list_scene",
            {"engine": "unreal", "target": "PlayerStart"},
            self.tools,
        )

        self.assertIsNotNone(call)
        self.assertEqual(call.tool_name, "get_actor_properties")
        self.assertEqual(call.arguments, {"name": "PlayerStart"})

    def test_create_object_maps_to_spawn_actor_payload(self) -> None:
        call = self.adapter.map_call(
            "engine_create_object",
            {
                "engine": "unreal",
                "name": "LF_TestCube",
                "object_type": "StaticMeshActor",
                "position": {"x": 10, "y": 20, "z": 30},
                "rotation": [0, 90, 0],
            },
            self.tools,
        )

        self.assertIsNotNone(call)
        self.assertEqual(call.tool_name, "spawn_actor")
        self.assertEqual(
            call.arguments,
            {
                "name": "LF_TestCube",
                "type": "StaticMeshActor",
                "location": [10.0, 20.0, 30.0],
                "rotation": [0.0, 90.0, 0.0],
            },
        )

    def test_move_object_maps_to_transform_payload(self) -> None:
        call = self.adapter.map_call(
            "engine_move_object",
            {
                "engine": "unreal",
                "target": "LF_TestCube",
                "position": [1, 2, 3],
                "scale": [2, 2, 2],
            },
            self.tools,
        )

        self.assertIsNotNone(call)
        self.assertEqual(call.tool_name, "set_actor_transform")
        self.assertEqual(
            call.arguments,
            {"name": "LF_TestCube", "location": [1.0, 2.0, 3.0], "scale": [2.0, 2.0, 2.0]},
        )

    def test_create_script_maps_to_blueprint_payload_without_workspace_path(self) -> None:
        call = self.adapter.map_call(
            "engine_create_script",
            {
                "engine": "unreal",
                "class_name": "BP_DemoEnemy",
                "properties": {"parent_class": "Character"},
            },
            self.tools,
        )

        self.assertIsNotNone(call)
        self.assertEqual(call.tool_name, "create_blueprint")
        self.assertEqual(call.arguments, {"name": "BP_DemoEnemy", "parent_class": "Character"})

    def test_save_scene_maps_to_save_level(self) -> None:
        call = self.adapter.map_call("engine_save_scene", {"engine": "unreal"}, self.tools)

        self.assertIsNotNone(call)
        self.assertEqual(call.tool_name, "save_level")
        self.assertEqual(call.arguments, {})
        self.assertEqual(call.operation_name, "unreal.level.save")

    def test_read_console_maps_to_output_log(self) -> None:
        call = self.adapter.map_call(
            "engine_read_console",
            {"engine": "unreal", "lines": 50},
            self.tools,
        )

        self.assertIsNotNone(call)
        self.assertEqual(call.tool_name, "read_output_log")
        self.assertEqual(call.arguments, {"lines": 50})
        self.assertEqual(call.operation_name, "unreal.output_log.read")

    def test_run_project_maps_to_pie(self) -> None:
        call = self.adapter.map_call(
            "engine_run_project",
            {"engine": "unreal", "mode": "pie"},
            self.tools,
        )

        self.assertIsNotNone(call)
        self.assertEqual(call.tool_name, "run_pie")
        self.assertEqual(call.arguments, {"action": "play"})
        self.assertEqual(call.operation_name, "unreal.pie.run")


if __name__ == "__main__":
    unittest.main()
