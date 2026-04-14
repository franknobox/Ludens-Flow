import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "src"))

os.chdir(_ROOT)
os.environ.setdefault(
    "LUDENS_WORKSPACE_DIR",
    str(
        (
            Path(tempfile.gettempdir()) / "ludens_flow_tests" / "test_regressions"
        ).resolve()
    ),
)

from ludens_flow.agents.base import AgentResult
from ludens_flow.agents.design_agent import DesignAgent
from ludens_flow.agents.engineering_agent import EngineeringAgent
from ludens_flow.agents.pm_agent import PMAgent
from ludens_flow.agents.review_agent import ReviewAgent
from ludens_flow.artifacts import read_artifact, write_artifact
from ludens_flow.graph import _merge_state_updates, run_agent_step
from ludens_flow.prompt_templates import load_prompt_template
from ludens_flow.schemas import parse_discuss_payload, parse_review_gate_payload
from ludens_flow.state import init_state, init_workspace, load_state
from ludens_flow.user_profile import (
    format_profile_for_prompt,
    load_profile,
    migrate_profile_file,
    migrate_profile_text_to_current_template,
)


class RegressionTests(unittest.TestCase):
    def setUp(self):
        init_workspace()

    def test_devlog_can_be_written_while_artifacts_are_frozen(self):
        state = init_state()
        state.phase = "DEV_COACHING"
        state.artifact_frozen = True

        write_artifact(
            "DEVLOG",
            "coach notes",
            reason="test",
            actor="EngineeringAgent",
            state=state,
        )

        self.assertIn("devlog", state.artifacts)
        self.assertEqual(state.artifacts["devlog"].version, 1)
        self.assertIn("coach notes", read_artifact("DEVLOG"))

    def test_pm_change_requests_only_append_new_entries(self):
        agent = PMAgent()
        agent._call = lambda *args, **kwargs: (
            "# PLAN\n"
            "<<CHANGE_REQUEST_JSON>>\n"
            '{"change_requests":[{"target":"GDD","rationale":"missing ending","suggested_changes":"add ending","severity":"High"}]}\n'
            "<<END_CHANGE_REQUEST_JSON>>"
        )

        state = init_state()
        state.change_requests = [{"target": "PM", "rationale": "existing"}]

        result = agent.commit(state, "commit")
        self.assertEqual(len(result.state_updates["change_requests"]), 1)

        _merge_state_updates(state, result.state_updates)
        self.assertEqual(len(state.change_requests), 2)
        self.assertEqual(state.change_requests[0]["target"], "PM")
        self.assertEqual(state.change_requests[1]["target"], "GDD")

    def test_engineering_style_preset_is_persisted_and_recoverable(self):
        agent = EngineeringAgent()
        agent._call = lambda *args, **kwargs: "mock reply"

        state = init_state()

        discuss_result = agent.plan_discuss(state, "We should use Preset B")
        self.assertEqual(discuss_result.state_updates.get("style_preset"), "B")

        state.style_preset = "B"
        commit_result = agent.plan_commit(state, "commit")
        self.assertEqual(
            commit_result.state_updates.get("decisions"), ["ENG committed"]
        )
        self.assertNotIn("style_preset", commit_result.state_updates)

        state.style_preset = None
        state.chat_history = [
            {"role": "user", "content": "This time choose Preset C and keep feature slices."},
            {"role": "assistant", "content": "Noted."},
        ]

        recovered_commit = agent.plan_commit(state, "commit")
        self.assertEqual(recovered_commit.state_updates.get("style_preset"), "C")

        recovered_coach = agent.coach(state, "What should I do next?")
        self.assertEqual(recovered_coach.state_updates.get("style_preset"), "C")

    def test_structured_response_parses_json_code_fence(self):
        agent = EngineeringAgent()
        parsed, remaining = agent.parse_structured_response(
            'prefix\n```json\n{"reply":"ok","state_updates":{"a":1}}\n```\nsuffix'
        )

        self.assertEqual(parsed["reply"], "ok")
        self.assertEqual(parsed["state_updates"]["a"], 1)
        self.assertEqual(remaining, "prefix\n\nsuffix")

    def test_structured_response_uses_shared_parser_for_nested_json(self):
        agent = EngineeringAgent()
        parsed, remaining = agent.parse_structured_response(
            'prefix\n<<STRUCTURED>>\n{"reply":"brace { ok }","state_updates":{"plan":{"mode":"mvp"}}}\n<<END_STRUCTURED>>\nsuffix'
        )

        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["reply"], "brace { ok }")
        self.assertEqual(parsed["state_updates"], {"plan": {"mode": "mvp"}})
        self.assertEqual(remaining, "prefix\n\nsuffix")

    def test_discuss_schema_normalizes_defaults_and_types(self):
        payload, remaining = parse_discuss_payload(
            '```json\n{"reply": 123, "state_updates": [], "profile_updates": "nickname: Alice", "events": "DONE"}\n```'
        )

        self.assertEqual(remaining, "")
        self.assertIsNotNone(payload)
        self.assertEqual(payload.reply, "123")
        self.assertEqual(payload.state_updates, {})
        self.assertEqual(payload.profile_updates, ["nickname: Alice"])
        self.assertEqual(payload.events, ["DONE"])

    def test_discuss_schema_ignores_braces_inside_reply_string(self):
        payload, remaining = parse_discuss_payload(
            '{"reply":"This is a { sample }","state_updates":{"nested":{"ok":true}},"profile_updates":[null,"nickname: Alice",""],"events":[null,"DONE","  "]}'
        )

        self.assertEqual(remaining, "")
        self.assertIsNotNone(payload)
        self.assertEqual(payload.reply, "This is a { sample }")
        self.assertEqual(payload.state_updates, {"nested": {"ok": True}})
        self.assertEqual(payload.profile_updates, ["nickname: Alice"])
        self.assertEqual(payload.events, ["DONE"])

    def test_discuss_schema_parses_nested_json_inside_code_fence(self):
        payload, remaining = parse_discuss_payload(
            'prefix\n```json\n{"reply":"ok","state_updates":{"plan":{"mode":"mvp","steps":["a","b"]}},"profile_updates":[],"events":["READY"]}\n```\nsuffix'
        )

        self.assertEqual(remaining, "prefix\n\nsuffix")
        self.assertIsNotNone(payload)
        self.assertEqual(payload.reply, "ok")
        self.assertEqual(
            payload.state_updates,
            {"plan": {"mode": "mvp", "steps": ["a", "b"]}},
        )
        self.assertEqual(payload.events, ["READY"])

    def test_discuss_schema_parses_nested_json_inside_tag_block(self):
        payload, remaining = parse_discuss_payload(
            'before\n<<DISCUSS_JSON>>\n{"reply":"tag ok","state_updates":{"choice":{"preset":"B"}},"profile_updates":[],"events":["TAGGED"]}\n<<END_DISCUSS_JSON>>\nafter'
        )

        self.assertEqual(remaining, "before\n\nafter")
        self.assertIsNotNone(payload)
        self.assertEqual(payload.reply, "tag ok")
        self.assertEqual(payload.state_updates, {"choice": {"preset": "B"}})
        self.assertEqual(payload.events, ["TAGGED"])

    def test_review_gate_schema_parses_tagged_nested_json(self):
        payload, remaining = parse_review_gate_payload(
            'report body\n<<REVIEW_GATE_JSON>>\n{"status":"REQUEST_CHANGES","targets":["ENG"],"scores":{"design":8,"engineering":5},"issues":[{"target":"ENG","severity":"MAJOR","summary":"brace { issue }","fix_hint":"split system"}]}\n<<END_REVIEW_GATE_JSON>>'
        )

        self.assertIsNotNone(payload)
        self.assertEqual(remaining, "report body")
        self.assertEqual(payload.status, "REQUEST_CHANGES")
        self.assertEqual(payload.targets, ["ENG"])
        self.assertEqual(payload.scores, {"design": 8.0, "engineering": 5.0})
        self.assertEqual(len(payload.issues), 1)
        self.assertEqual(payload.issues[0].summary, "brace { issue }")

    def test_review_agent_applies_block_rule_after_schema_parse(self):
        agent = ReviewAgent()
        payload, clean_md = agent._parse_review_gate(
            'markdown\n<<REVIEW_GATE_JSON>>\n{"status":"PASS","targets":[],"scores":{"design":9,"engineering":9},"issues":[{"target":"ENG","severity":"BLOCK","summary":"fatal","fix_hint":"redo"}]}\n<<END_REVIEW_GATE_JSON>>'
        )

        self.assertEqual(clean_md, "markdown")
        self.assertEqual(payload.status, "BLOCK")

    def test_engineering_prompt_template_loads_layered_sections(self):
        template = load_prompt_template("engineering_agent.md")

        self.assertIsNotNone(template)
        self.assertIn("Eon", template.role_persona)
        self.assertIn("Architecture / Planning", template.task_instruction)
        self.assertIn("Continuous Development / Coaching", template.task_instruction)
        self.assertIn("项目上下文", template.context_injection)
        self.assertIn("结构化输出", template.output_contract)
        self.assertIn("[PROFILE_UPDATE]", template.profile_instruction)
        self.assertIn("## Role & Persona", template.build_system_prompt())

    def test_all_agent_prompt_templates_load_layered_sections(self):
        expectations = {
            "design_agent.md": "Dam",
            "pm_agent.md": "Pax",
            "review_agent.md": "Revs",
        }

        for filename, marker in expectations.items():
            template = load_prompt_template(filename)
            self.assertIsNotNone(template)
            self.assertIn(marker, template.role_persona)
            self.assertTrue(template.task_instruction.strip())
            self.assertTrue(template.context_injection.strip())
            self.assertTrue(template.output_contract.strip())
            self.assertIn("[PROFILE_UPDATE]", template.profile_instruction)
            self.assertIn("## Output Contract", template.build_system_prompt())

    def test_profile_prompt_formatter_adds_rules_and_structure(self):
        formatted = format_profile_for_prompt(
            "# User Profile\n\n> note\n\n## Basics\n- nickname: Alice\n- project_goals: Build a small Unity demo"
        )

        self.assertIn("[PROFILE USAGE RULES]", formatted)
        self.assertIn("[USER PROFILE CONTEXT]", formatted)
        self.assertIn("[Section] User Profile", formatted)
        self.assertIn("[Section] Basics", formatted)
        self.assertIn("- nickname: Alice", formatted)

    def test_load_profile_creates_structured_template(self):
        workspace_root = Path(tempfile.gettempdir()) / "ludens_flow_tests" / "profile_template"
        if workspace_root.exists():
            shutil.rmtree(workspace_root)

        with patch.dict(os.environ, {"LUDENS_WORKSPACE_DIR": str(workspace_root)}):
            text = load_profile(project_id="template-check")

        self.assertIn("# USER_PROFILE", text)
        self.assertIn("## Core Identity", text)
        self.assertIn("## Preferences", text)
        self.assertIn("## Project Context", text)
        self.assertIn("## Agent Working Notes", text)

    def test_migrate_profile_text_to_current_template_preserves_legacy_fields(self):
        legacy = """# 玩家/开发者画像 (USER_PROFILE)

## 👤 基础身份
- **代号/昵称**: Alice
- **核心诉求**: 做一个可玩的 Unity Demo
- **当前状态**: 周末开发者

## 🛠 技术与能力栈
- **引擎熟练度**: Unity 新手
- **编程能力**: C# 基础薄弱
- **美术能力**: 0 美术基础
- **短板警报**: 害怕 Shader

## 🎨 审美与开发偏好
- **核心游戏品类**: 2D 平台跳跃
- **视觉风格**: 极简多边形
- **沟通偏好**: 希望先给结论

## ⏱ 项目限制与边界
- **工期预期**: 1 个月 Demo
- **资源限制**: 预算 0
- **工具链偏好**: Unity + VS Code

## 🧠 Agent 阶段观察记录 (动态更新区)
### 🔍 [Design 观察]
- 喜欢轻量玩法
### 📅 [PM 观察]
- 需要强 scope 控制
### 💻 [Eng 观察]
- 害怕复杂系统
"""
        migrated = migrate_profile_text_to_current_template(legacy)

        self.assertIn("# USER_PROFILE", migrated)
        self.assertIn("- nickname: Alice", migrated)
        self.assertIn("- current_working_mode: 周末开发者", migrated)
        self.assertIn("- gameplay_preferences: 2D 平台跳跃", migrated)
        self.assertIn("- current_project_goal: 做一个可玩的 Unity Demo", migrated)
        self.assertIn("## Migrated Legacy Details", migrated)
        self.assertIn("- engine_skill: Unity 新手", migrated)
        self.assertIn("### Design", migrated)
        self.assertIn("- 喜欢轻量玩法", migrated)

    def test_migrate_profile_file_updates_legacy_profile(self):
        workspace_root = Path(tempfile.gettempdir()) / "ludens_flow_tests" / "profile_migration"
        if workspace_root.exists():
            shutil.rmtree(workspace_root)

        legacy_profile = """# 玩家/开发者画像 (USER_PROFILE)

## 👤 基础身份
- **代号/昵称**: Alice
- **核心诉求**: 做一个可玩的 Unity Demo
- **当前状态**: 周末开发者
"""

        with patch.dict(os.environ, {"LUDENS_WORKSPACE_DIR": str(workspace_root)}):
            profile_dir = workspace_root / "projects" / "migrate-me"
            profile_dir.mkdir(parents=True, exist_ok=True)
            (profile_dir / "USER_PROFILE.md").write_text(legacy_profile, encoding="utf-8")

            changed = migrate_profile_file(project_id="migrate-me")
            migrated = (profile_dir / "USER_PROFILE.md").read_text(encoding="utf-8")

        self.assertTrue(changed)
        self.assertIn("# USER_PROFILE", migrated)
        self.assertIn("- nickname: Alice", migrated)

    def test_run_agent_step_passes_structured_profile_context(self):
        agent = DesignAgent()
        agent.system_prompt = "original prompt"
        captured = {}

        def fake_discuss(*args, **kwargs):
            captured["user_persona"] = kwargs.get("user_persona", "")
            return AgentResult(assistant_message="ok")

        agent.discuss = fake_discuss

        state = load_state(project_id="alpha")
        state.phase = "GDD_DISCUSS"

        with patch(
            "ludens_flow.user_profile.load_profile",
            return_value="# User Profile\n\n## Basics\n- nickname: Alice\n- preferences: minimal UI",
        ):
            run_agent_step(agent, "DISCUSS", state, "hello")

        self.assertIn("[PROFILE USAGE RULES]", captured["user_persona"])
        self.assertIn("[USER PROFILE CONTEXT]", captured["user_persona"])
        self.assertIn("[Section] Basics", captured["user_persona"])
        self.assertIn("nickname: Alice", captured["user_persona"])

    def test_run_agent_step_uses_project_scoped_profile_and_restores_prompt(self):
        agent = DesignAgent()
        original_prompt = "original prompt"
        agent.system_prompt = original_prompt
        agent.discuss = lambda *args, **kwargs: AgentResult(assistant_message="ok")

        state = load_state(project_id="alpha")
        state.phase = "GDD_DISCUSS"

        with patch(
            "ludens_flow.user_profile.load_profile", return_value="profile text"
        ) as mocked_load:
            run_agent_step(agent, "DISCUSS", state, "hello")

        mocked_load.assert_called_once_with(max_chars=2000, project_id="alpha")
        self.assertEqual(agent.system_prompt, original_prompt)


if __name__ == "__main__":
    unittest.main()
