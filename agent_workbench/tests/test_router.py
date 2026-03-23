import logging
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
    str((Path(tempfile.gettempdir()) / "ludens_flow_tests" / "test_router").resolve()),
)

from ludens_flow.router import Phase, route
from ludens_flow.state import init_state

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


class RouterTests(unittest.TestCase):
    def test_discuss_phase_actions(self):
        state = init_state()

        state.phase = Phase.PM_DISCUSS.value
        next_phase, _, _ = route(state, "1")
        self.assertEqual(next_phase, Phase.PM_DISCUSS.value)

        state.phase = Phase.PM_DISCUSS.value
        next_phase, _, _ = route(state, "定稿")
        self.assertEqual(next_phase, Phase.PM_COMMIT.value)

        state.phase = Phase.PM_DISCUSS.value
        next_phase, _, _ = route(state, "3")
        self.assertEqual(next_phase, Phase.GDD_DISCUSS.value)

    def test_default_commit_event_transitions(self):
        state = init_state()

        state.phase = Phase.GDD_COMMIT.value
        next_phase, _, _ = route(state, "", last_event="GDD_COMMITTED")
        self.assertEqual(next_phase, Phase.PM_DISCUSS.value)

        state.phase = Phase.PM_COMMIT.value
        next_phase, _, _ = route(state, "", last_event="PM_COMMITTED")
        self.assertEqual(next_phase, Phase.ENG_DISCUSS.value)

    def test_review_done_without_decision_pauses_for_user(self):
        state = init_state()
        state.phase = Phase.REVIEW.value
        state.review_gate = {"status": "REQUEST_CHANGES", "targets": ["PM"], "issues": []}

        next_phase, _, _ = route(state, "", last_event="REVIEW_DONE")
        self.assertEqual(next_phase, Phase.POST_REVIEW_DECISION.value)

    def test_post_review_option_a_flows_back_to_targets(self):
        state = init_state()
        state.phase = Phase.POST_REVIEW_DECISION.value
        state.iteration_count = 0
        state.review_gate = {
            "status": "REQUEST_CHANGES",
            "targets": ["ENG"],
            "issues": [{"target": "ENG", "severity": "MINOR"}],
        }

        next_phase, _, updates = route(state, "a")
        self.assertEqual(next_phase, Phase.ENG_DISCUSS.value)
        self.assertEqual(updates.get("iteration_count"), 1)

    def test_post_review_option_b_filters_major_and_block(self):
        state = init_state()
        state.phase = Phase.POST_REVIEW_DECISION.value
        state.review_gate = {
            "status": "REQUEST_CHANGES",
            "targets": ["ENG"],
            "issues": [{"target": "ENG", "severity": "MINOR"}],
        }

        next_phase, _, updates = route(state, "b")
        self.assertEqual(next_phase, Phase.DEV_COACHING.value)
        self.assertTrue(updates.get("artifact_frozen"))

        state.phase = Phase.POST_REVIEW_DECISION.value
        state.review_gate["issues"] = [
            {"target": "ENG", "severity": "MINOR"},
            {"target": "PM", "severity": "MAJOR"},
        ]
        next_phase, _, updates = route(state, "b")
        self.assertEqual(next_phase, Phase.PM_DISCUSS.value)
        self.assertEqual(updates.get("iteration_count"), 1)

    def test_post_review_option_c_enters_dev_coaching(self):
        state = init_state()
        state.phase = Phase.POST_REVIEW_DECISION.value
        state.review_gate = {"status": "REQUEST_CHANGES", "targets": ["GDD"], "issues": []}

        next_phase, _, updates = route(state, "c")
        self.assertEqual(next_phase, Phase.DEV_COACHING.value)
        self.assertTrue(updates.get("artifact_frozen"))

    def test_dev_coaching_freeze_and_unfreeze_behavior(self):
        state = init_state()
        state.phase = Phase.DEV_COACHING.value
        state.artifact_frozen = True

        next_phase, _, updates = route(state, "这段代码怎么写？")
        self.assertEqual(next_phase, Phase.DEV_COACHING.value)
        self.assertTrue(updates.get("artifact_frozen"))

        next_phase, _, updates = route(state, "定稿")
        self.assertEqual(next_phase, Phase.DEV_COACHING.value)
        self.assertTrue(updates.get("artifact_frozen"))

        next_phase, _, updates = route(state, "解冻")
        self.assertEqual(next_phase, Phase.ENG_DISCUSS.value)
        self.assertFalse(updates.get("artifact_frozen"))

    def test_iteration_limit_forces_dev_coaching(self):
        state = init_state()
        state.phase = Phase.GDD_DISCUSS.value
        state.iteration_count = 10

        next_phase, _, updates = route(state, "随便")
        self.assertEqual(next_phase, Phase.DEV_COACHING.value)
        self.assertTrue(updates.get("artifact_frozen"))


if __name__ == "__main__":
    unittest.main()
