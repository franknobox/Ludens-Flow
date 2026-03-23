import os
import sys
import tempfile
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "src"))

os.chdir(_ROOT)
os.environ.setdefault(
    "LUDENS_WORKSPACE_DIR",
    str((Path(tempfile.gettempdir()) / "ludens_flow_tests" / "test_regressions").resolve()),
)

from ludens_flow.agents.pm_agent import PMAgent
from ludens_flow.artifacts import read_artifact, write_artifact
from ludens_flow.graph import _merge_state_updates
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


if __name__ == "__main__":
    unittest.main()
