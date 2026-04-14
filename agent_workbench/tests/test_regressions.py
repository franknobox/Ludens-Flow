import os
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
from ludens_flow.schemas import parse_discuss_payload, parse_review_gate_payload
from ludens_flow.state import init_state, init_workspace, load_state


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
