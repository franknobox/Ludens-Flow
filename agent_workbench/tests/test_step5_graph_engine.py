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

import ludens_flow.core.state as st
from ludens_flow.core.agents.base import AgentResult, CommitSpec
from ludens_flow.core.agents.design_agent import DesignAgent
from ludens_flow.core.agents.engineering_agent import EngineeringAgent
from ludens_flow.core.agents.pm_agent import PMAgent
from ludens_flow.core.agents.review_agent import ReviewAgent
from ludens_flow.core.graph import graph_step, run_agent_step
from ludens_flow.core.router import Phase


def mock_design_discuss(
    self,
    state,
    user_input,
    cfg=None,
    user_persona=None,
    stream_handler=None,
    tool_event_handler=None,
):
    return AgentResult(
        assistant_message="design ok",
        state_updates={"drafts": {"gdd": {"core_loop": "combat"}}},
    )


def mock_design_commit(
    self,
    state,
    user_input,
    cfg=None,
    user_persona=None,
    tool_event_handler=None,
):
    return AgentResult(
        assistant_message="",
        commit=CommitSpec(artifact_name="GDD", content="gdd\n", reason="test"),
        state_updates={},
    )


def mock_pm_discuss(
    self,
    state,
    user_input,
    cfg=None,
    user_persona=None,
    stream_handler=None,
    tool_event_handler=None,
):
    return AgentResult(assistant_message="pm ok", state_updates={})


def mock_pm_commit(
    self,
    state,
    user_input,
    cfg=None,
    user_persona=None,
    tool_event_handler=None,
):
    return AgentResult(
        assistant_message="",
        commit=CommitSpec(
            artifact_name="PROJECT_PLAN",
            content="plan\n",
            reason="test",
        ),
        state_updates={},
    )


def mock_eng_discuss(
    self,
    state,
    user_input,
    cfg=None,
    user_persona=None,
    stream_handler=None,
    tool_event_handler=None,
):
    return AgentResult(
        assistant_message="eng ok",
        state_updates={"style_preset": "OOP"},
    )


def mock_eng_commit(
    self,
    state,
    user_input,
    cfg=None,
    user_persona=None,
    tool_event_handler=None,
):
    return AgentResult(
        assistant_message="",
        commit=CommitSpec(
            artifact_name="IMPLEMENTATION_PLAN",
            content="impl\n",
            reason="test",
        ),
        state_updates={},
    )


def mock_eng_coach(
    self,
    state,
    user_input,
    cfg=None,
    user_persona=None,
    stream_handler=None,
    tool_event_handler=None,
):
    return AgentResult(assistant_message="coach", state_updates={})


class Step5GraphEngineTests(unittest.TestCase):
    def setUp(self):
        self.previous_workspace = os.environ.get("LUDENS_WORKSPACE_DIR")
        self.previous_project = os.environ.get("LUDENS_PROJECT_ID")
        self.workspace_root = (_ROOT / "workspace_test_step5_graph_engine").resolve()
        shutil.rmtree(self.workspace_root, ignore_errors=True)
        os.environ["LUDENS_WORKSPACE_DIR"] = str(self.workspace_root)
        os.environ.pop("LUDENS_PROJECT_ID", None)
        st.init_workspace()

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

    def test_main_flow_handles_review_backflow_and_reaches_dev_coaching(self):
        review_counter = {"count": 0}

        def review_commit(
            self,
            state,
            user_input,
            cfg=None,
            user_persona=None,
            tool_event_handler=None,
        ):
            if review_counter["count"] == 0:
                review_counter["count"] += 1
                gate = {
                    "status": "REQUEST_CHANGES",
                    "targets": ["ENG"],
                    "issues": [{"target": "ENG", "severity": "MAJOR"}],
                }
            else:
                gate = {
                    "status": "PASS",
                    "targets": [],
                    "issues": [],
                }

            return AgentResult(
                assistant_message="",
                commit=CommitSpec(
                    artifact_name="REVIEW_REPORT",
                    content="review\n",
                    reason="test",
                ),
                state_updates={"review_gate": gate},
            )

        with (
            patch.object(DesignAgent, "discuss", mock_design_discuss),
            patch.object(DesignAgent, "commit", mock_design_commit),
            patch.object(PMAgent, "discuss", mock_pm_discuss),
            patch.object(PMAgent, "commit", mock_pm_commit),
            patch.object(EngineeringAgent, "plan_discuss", mock_eng_discuss),
            patch.object(EngineeringAgent, "plan_commit", mock_eng_commit),
            patch.object(EngineeringAgent, "coach", mock_eng_coach),
            patch.object(ReviewAgent, "commit", review_commit),
        ):
            state = st.load_state()
            self.assertEqual(state.phase, Phase.GDD_DISCUSS.value)

            state = graph_step(state, "gdd discuss")
            state = graph_step(state, "[ACTION] commit gdd", explicit_action="gdd_commit")
            state = graph_step(state, "")
            self.assertEqual(state.phase, Phase.PM_DISCUSS.value)

            state = graph_step(state, "pm discuss")
            state = graph_step(state, "[ACTION] commit pm", explicit_action="pm_commit")
            state = graph_step(state, "")
            self.assertEqual(state.phase, Phase.ENG_DISCUSS.value)

            state = graph_step(state, "eng discuss")
            state = graph_step(state, "[ACTION] commit eng", explicit_action="eng_commit")
            state = graph_step(state, "")
            self.assertEqual(state.phase, Phase.REVIEW.value)

            state = graph_step(state, "")
            self.assertEqual(state.phase, Phase.REVIEW.value)

            state = graph_step(state, "")
            self.assertEqual(state.phase, Phase.POST_REVIEW_DECISION.value)

            state = graph_step(state, "[ACTION] option a", explicit_action="review_option_a")
            self.assertEqual(state.phase, Phase.ENG_DISCUSS.value)

            state = graph_step(state, "eng discuss again")
            state = graph_step(state, "[ACTION] commit eng", explicit_action="eng_commit")
            state = graph_step(state, "")
            self.assertEqual(state.phase, Phase.REVIEW.value)

            state = graph_step(state, "")
            self.assertEqual(state.phase, Phase.REVIEW.value)

            state = graph_step(state, "")
            self.assertEqual(state.phase, Phase.DEV_COACHING.value)
            self.assertTrue(state.artifact_frozen)

            state = graph_step(state, "解冻")
            self.assertEqual(state.phase, Phase.ENG_DISCUSS.value)
            self.assertFalse(state.artifact_frozen)

    def test_frozen_guard_blocks_plan_commit_during_dev_coaching(self):
        state = st.load_state()
        state.phase = Phase.DEV_COACHING.value
        state.artifact_frozen = True

        with patch.object(EngineeringAgent, "plan_commit", mock_eng_commit):
            state = run_agent_step(EngineeringAgent(), "PLAN_COMMIT", state, "commit")

        self.assertIsNotNone(state.last_error)
        self.assertIn("Cannot commit canonical artifact", state.last_error)
        self.assertEqual(state.phase, Phase.DEV_COACHING.value)

    def test_timeout_error_uses_unified_recovery_strategy(self):
        state = st.load_state()
        state.phase = Phase.GDD_DISCUSS.value
        agent = DesignAgent()

        def raise_timeout(*args, **kwargs):
            raise TimeoutError("mock timeout")

        agent.discuss = raise_timeout

        result = run_agent_step(agent, "DISCUSS", state, "hello")
        self.assertEqual(result.phase, Phase.GDD_DISCUSS.value)
        self.assertTrue((result.last_error or "").startswith("[TIMEOUT]"))
        self.assertIn("DesignAgent", result.last_assistant_message or "")

    def test_parse_error_uses_unified_recovery_strategy(self):
        state = st.load_state()
        state.phase = Phase.GDD_DISCUSS.value
        agent = DesignAgent()

        def empty_discuss(*args, **kwargs):
            return AgentResult(assistant_message="", state_updates={})

        agent.discuss = empty_discuss

        result = run_agent_step(agent, "DISCUSS", state, "hello")
        self.assertEqual(result.phase, Phase.GDD_DISCUSS.value)
        self.assertTrue((result.last_error or "").startswith("[PARSE]"))
        self.assertIn("DesignAgent", result.last_assistant_message or "")


if __name__ == "__main__":
    unittest.main()
