import os
import shutil
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "src"))

os.chdir(_ROOT)

from ludens_flow.core.state import init_workspace
from llm.provider import LLMConfig


class GameModelRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.previous_workspace = os.environ.get("LUDENS_WORKSPACE_DIR")
        self.previous_project = os.environ.get("LUDENS_PROJECT_ID")
        self.workspace_root = (_ROOT / "workspace_test_game_model_runtime").resolve()
        shutil.rmtree(self.workspace_root, ignore_errors=True)
        os.environ["LUDENS_WORKSPACE_DIR"] = str(self.workspace_root)
        os.environ.pop("LUDENS_PROJECT_ID", None)
        init_workspace()

    def tearDown(self):
        shutil.rmtree(self.workspace_root, ignore_errors=True)
        if self.previous_workspace is None:
            os.environ.pop("LUDENS_WORKSPACE_DIR", None)
        else:
            os.environ["LUDENS_WORKSPACE_DIR"] = self.previous_workspace

        if self.previous_project is None:
            os.environ.pop("LUDENS_PROJECT_ID", None)
        else:
            os.environ["LUDENS_PROJECT_ID"] = self.previous_project

    def test_runtime_state_exposes_required_scenarios(self):
        from ludens_flow.capabilities.game_model.runtime import build_runtime_state

        state = build_runtime_state(project_id="alpha")

        self.assertEqual(state["project_id"], "alpha")
        scene_ids = {scene["id"] for scene in state["scenes"]}
        self.assertIn("character-behavior-tree", scene_ids)
        self.assertIn("questline-generator", scene_ids)
        self.assertIn("multimodal-runtime", scene_ids)
        self.assertIn("world-model-coming-soon", scene_ids)
        self.assertEqual(state["world_model"]["status"], "coming_soon")
        self.assertGreaterEqual(len(state["world_model"]["milestones"]), 3)
        self.assertIn("配置", " -> ".join(state["runtime_pipeline"]["steps"]))
        self.assertIn("导出", " -> ".join(state["runtime_pipeline"]["steps"]))

    def test_api_can_persist_project_runtime_scene_configuration(self):
        import ludens_flow.app.api as api

        api.post_project(api.ProjectRequest(project_id="alpha"))
        scene = {
            "id": "custom-runtime-npc",
            "name": "自定义运行时 NPC",
            "category": "npc",
            "modelId": "gpt-5.4-mini",
            "systemPrompt": "只回答 20 字以内，并使用项目工具。",
            "temperature": 0.6,
            "maxTokens": 120,
            "tools": ["npc_memory_read", "quest_state_query"],
            "testInput": "玩家：你是谁？",
            "runtimeStage": "ready",
        }

        updated = api.post_current_project_game_model_runtime_scenes(
            api.GameModelRuntimeScenesRequest(scenes=[scene])
        )
        reloaded = api.get_current_project_game_model_runtime()

        self.assertEqual(updated["project_id"], "alpha")
        self.assertEqual(reloaded["scenes"][0]["id"], "custom-runtime-npc")
        self.assertEqual(reloaded["scenes"][0]["systemPrompt"], scene["systemPrompt"])
        self.assertIn("quest_state_query", reloaded["scenes"][0]["tools"])

    def test_api_runtime_scene_save_replaces_removed_scenes(self):
        import ludens_flow.app.api as api

        api.post_project(api.ProjectRequest(project_id="alpha"))
        first_scene = {
            "id": "keep-scene",
            "name": "保留场景",
            "category": "npc",
            "modelId": "gpt-5.4-mini",
            "systemPrompt": "保留。",
            "temperature": 0.5,
            "maxTokens": 120,
            "tools": [],
            "testInput": "",
            "runtimeStage": "ready",
        }
        removed_scene = {
            **first_scene,
            "id": "remove-scene",
            "name": "删除场景",
            "systemPrompt": "应被删除。",
        }

        api.post_current_project_game_model_runtime_scenes(
            api.GameModelRuntimeScenesRequest(scenes=[first_scene, removed_scene])
        )
        api.post_current_project_game_model_runtime_scenes(
            api.GameModelRuntimeScenesRequest(scenes=[first_scene])
        )

        reloaded = api.get_current_project_game_model_runtime()
        scene_ids = {scene["id"] for scene in reloaded["scenes"]}
        self.assertIn("keep-scene", scene_ids)
        self.assertNotIn("remove-scene", scene_ids)

    def test_behavior_tree_generation_returns_runtime_ready_structure(self):
        from ludens_flow.capabilities.game_model.runtime import generate_behavior_tree

        artifact = generate_behavior_tree(
            {
                "scene_id": "character-behavior-tree",
                "character_name": "黑木林巡逻兵",
                "goal": "发现玩家后先警戒、呼叫同伴，再根据血量决定追击或撤退。",
                "context": "第三人称动作 RPG，敌人有听觉和视觉感知。",
                "traits": ["谨慎", "会协作"],
            }
        )

        self.assertEqual(artifact["artifact_type"], "behavior_tree")
        self.assertEqual(artifact["character"]["name"], "黑木林巡逻兵")
        node_types = {node["type"] for node in artifact["tree"]["nodes"]}
        self.assertIn("selector", node_types)
        self.assertIn("sequence", node_types)
        self.assertIn("action", node_types)
        self.assertTrue(artifact["tree"]["transitions"])
        self.assertIn("TargetActor", {item["key"] for item in artifact["blackboard"]})
        self.assertEqual(
            artifact["unity_mapping"]["component"],
            "LudensBehaviorTreeRunner",
        )
        self.assertIn("JSON", artifact["llm_prompt_contract"]["output_format"])

    def test_questline_generation_returns_dependencies_and_runtime_contract(self):
        from ludens_flow.capabilities.game_model.runtime import generate_questline

        artifact = generate_questline(
            {
                "scene_id": "questline-generator",
                "theme": "黑木林兽人集结",
                "player_level": 20,
                "region": "黑木林",
                "beats": ["侦查", "救援", "破坏补给", "首领战"],
            }
        )

        self.assertEqual(artifact["artifact_type"], "questline")
        self.assertGreaterEqual(len(artifact["quests"]), 3)
        self.assertEqual(artifact["quests"][0]["depends_on"], [])
        self.assertTrue(artifact["quests"][1]["depends_on"])
        self.assertTrue(artifact["quests"][0]["objectives"])
        self.assertIn("quest_state", {item["key"] for item in artifact["runtime_variables"]})
        self.assertIn("complete_objective", artifact["server_contract"]["events"])
        self.assertEqual(artifact["unity_mapping"]["component"], "LudensQuestlineRunner")

    def test_multimodal_plan_covers_image_audio_and_video_inputs(self):
        from ludens_flow.capabilities.game_model.runtime import build_multimodal_plan

        plan = build_multimodal_plan(
            {
                "scene_id": "multimodal-runtime",
                "purpose": "分析玩家战斗录像、语音反馈和截图，给出可复现问题线索。",
                "modalities": ["image", "audio", "video"],
            }
        )

        self.assertEqual(plan["artifact_type"], "multimodal_plan")
        inputs = {item["modality"]: item for item in plan["inputs"]}
        self.assertIn("image", inputs)
        self.assertIn("audio", inputs)
        self.assertIn("video", inputs)
        self.assertIn("player_consent", plan["permissions"])
        self.assertLessEqual(inputs["video"]["limits"]["max_seconds"], 120)
        self.assertIn("attachments", plan["test_payload"])
        self.assertIn("cost_guardrails", plan)

    def test_runtime_export_bundle_contains_unity_and_rest_contracts(self):
        from ludens_flow.capabilities.game_model.runtime import build_runtime_export

        bundle = build_runtime_export(
            {
                "project_id": "alpha",
                "scene_ids": ["character-behavior-tree", "questline-generator", "multimodal-runtime"],
            }
        )

        self.assertEqual(bundle["artifact_type"], "runtime_export_bundle")
        self.assertIn("runtime_config.json", bundle["files"])
        self.assertIn("LudensFlowRuntimeClient.cs", bundle["files"])
        self.assertIn("LudensFlowAgentBinder.cs", bundle["files"])
        self.assertEqual(bundle["runtime_config"]["project_id"], "alpha")
        self.assertIn("/runtime/invoke", bundle["rest_contract"]["endpoints"])
        self.assertIn("Unity", " ".join(bundle["deployment_checklist"]))

    def test_runtime_scene_test_returns_prompt_tool_and_debug_trace(self):
        from ludens_flow.capabilities.game_model.runtime import run_runtime_scene_test

        result = run_runtime_scene_test(
            {
                "scene_id": "npc-dialogue-runtime",
                "input": "玩家：黑木林入口现在安全吗？",
            }
        )

        self.assertEqual(result["artifact_type"], "runtime_test_result")
        self.assertEqual(result["scene_id"], "npc-dialogue-runtime")
        self.assertIn("system_prompt", result["request"])
        self.assertIn("tools", result["request"])
        self.assertIn("quest_state_query", result["request"]["tools"])
        self.assertEqual(result["request"]["runtime_params"]["temperature"], 0.7)
        self.assertIn("response", result)
        self.assertIn("debug", result)
        self.assertEqual(result["debug"]["mode"], "deterministic_runtime_preview")

    def test_runtime_scene_test_can_use_live_model_routing_when_requested(self):
        from ludens_flow.capabilities.game_model.runtime import run_runtime_scene_test

        cfg = LLMConfig(
            provider="openai",
            model="unit-test-model",
            api_key="unit-test-key",
            temperature=0.4,
        )
        with patch(
            "ludens_flow.capabilities.game_model.runtime.resolve_model_config",
            return_value=cfg,
        ) as resolve_model_config, patch(
            "ludens_flow.capabilities.game_model.runtime.generate_llm",
            return_value="现场模型回复",
        ) as generate_llm:
            result = run_runtime_scene_test(
                {
                    "project_id": "alpha",
                    "scene_id": "npc-dialogue-runtime",
                    "input": "玩家：黑木林入口现在安全吗？",
                    "live_model": True,
                }
            )

        self.assertEqual(result["artifact_type"], "runtime_test_result")
        self.assertEqual(result["response"]["type"], "llm_text")
        self.assertEqual(result["response"]["text"], "现场模型回复")
        self.assertEqual(result["debug"]["mode"], "live_model")
        self.assertEqual(result["debug"]["model"], "unit-test-model")
        resolve_model_config.assert_called_once()
        generate_llm.assert_called_once()
        call_kwargs = generate_llm.call_args.kwargs
        self.assertIn("NPC", call_kwargs["system"])
        self.assertIn("黑木林", call_kwargs["user"])

    def test_api_routes_are_registered_and_return_runtime_artifacts(self):
        import ludens_flow.app.api as api

        api.post_project(api.ProjectRequest(project_id="alpha"))
        paths = {getattr(route, "path", "") for route in api.app.routes}

        self.assertIn("/api/projects/current/game-model/runtime", paths)
        self.assertIn("/api/projects/current/game-model/behavior-tree", paths)
        self.assertIn("/api/projects/current/game-model/questline", paths)
        self.assertIn("/api/projects/current/game-model/multimodal-plan", paths)
        self.assertIn("/api/projects/current/game-model/runtime/test", paths)
        self.assertIn("/api/projects/current/game-model/export", paths)

        state = api.get_current_project_game_model_runtime()
        self.assertEqual(state["project_id"], "alpha")

        tree = api.post_current_project_game_model_behavior_tree(
            api.GameModelGenerationRequest(character_name="巡逻兵")
        )
        self.assertEqual(tree["artifact_type"], "behavior_tree")

        questline = api.post_current_project_game_model_questline(
            api.GameModelGenerationRequest(theme="黑木林危机")
        )
        self.assertEqual(questline["artifact_type"], "questline")

        plan = api.post_current_project_game_model_multimodal_plan(
            api.GameModelGenerationRequest(modalities=["image", "audio", "video"])
        )
        self.assertEqual(plan["artifact_type"], "multimodal_plan")

        runtime_test = api.post_current_project_game_model_runtime_test(
            api.GameModelRuntimeTestRequest(
                scene_id="npc-dialogue-runtime",
                input="玩家：黑木林入口现在安全吗？",
            )
        )
        self.assertEqual(runtime_test["artifact_type"], "runtime_test_result")

        bundle = api.post_current_project_game_model_export(
            api.GameModelExportRequest(scene_ids=["character-behavior-tree"])
        )
        self.assertEqual(bundle["artifact_type"], "runtime_export_bundle")


if __name__ == "__main__":
    unittest.main()
