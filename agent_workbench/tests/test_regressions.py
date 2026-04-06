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
    str((Path(tempfile.gettempdir()) / "ludens_flow_tests" / "test_regressions").resolve()),
)

from ludens_flow.agents.base import AgentResult
from ludens_flow.agents.design_agent import DesignAgent
from ludens_flow.agents.engineering_agent import EngineeringAgent
from ludens_flow.agents.pm_agent import PMAgent
from ludens_flow.artifacts import read_artifact, write_artifact
from ludens_flow.graph import _merge_state_updates, run_agent_step
from ludens_flow.state import init_state, init_workspace


class RegressionTests(unittest.TestCase):
    def setUp(self):
        init_workspace()

    def test_devlog_can_be_written_while_artifacts_are_frozen(self):
        state = init_state()
        state.phase = "DEV_COACHING"
        state.artifact_frozen = True

        write_artifact("DEVLOG", "coach notes", reason="test", actor="EngineeringAgent", state=state)

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

        result = agent.commit(state, "定稿")
        self.assertEqual(len(result.state_updates["change_requests"]), 1)

        _merge_state_updates(state, result.state_updates)
        self.assertEqual(len(state.change_requests), 2)
        self.assertEqual(state.change_requests[0]["target"], "PM")
        self.assertEqual(state.change_requests[1]["target"], "GDD")

    def test_engineering_style_preset_is_persisted_and_recoverable(self):
        agent = EngineeringAgent()
        agent._call = lambda *args, **kwargs: "mock reply"

        state = init_state()

        discuss_result = agent.plan_discuss(state, "我们就用 Preset B")
        self.assertEqual(discuss_result.state_updates.get("style_preset"), "B")

        state.style_preset = "B"
        commit_result = agent.plan_commit(state, "定稿")
        self.assertEqual(commit_result.state_updates.get("decisions"), ["ENG committed"])
        self.assertNotIn("style_preset", commit_result.state_updates)

        state.style_preset = None
        state.chat_history = [
            {"role": "user", "content": "这次选 Preset C，保持 feature slice。"},
            {"role": "assistant", "content": "收到。"},
        ]

        recovered_commit = agent.plan_commit(state, "定稿")
        self.assertEqual(recovered_commit.state_updates.get("style_preset"), "C")

        recovered_coach = agent.coach(state, "下一步怎么落地？")
        self.assertEqual(recovered_coach.state_updates.get("style_preset"), "C")

    def test_structured_response_parses_json_code_fence(self):
        agent = EngineeringAgent()
        parsed, remaining = agent.parse_structured_response(
            'prefix\n```json\n{"reply":"ok","state_updates":{"a":1}}\n```\nsuffix'
        )

        self.assertEqual(parsed["reply"], "ok")
        self.assertEqual(parsed["state_updates"]["a"], 1)
        self.assertEqual(remaining, "prefix\n\nsuffix")

    def test_run_agent_step_uses_project_scoped_profile_and_restores_prompt(self):
        agent = DesignAgent()
        original_prompt = "original prompt"
        agent.system_prompt = original_prompt
        agent.discuss = lambda *args, **kwargs: AgentResult(assistant_message="ok")

        state = init_state(project_id="alpha")
        state.phase = "GDD_DISCUSS"

        with patch("ludens_flow.user_profile.load_profile", return_value="profile text") as mocked_load:
            run_agent_step(agent, "DISCUSS", state, "hello")

        mocked_load.assert_called_once_with(max_chars=2000, project_id="alpha")
        self.assertEqual(agent.system_prompt, original_prompt)


if __name__ == "__main__":
    unittest.main()
