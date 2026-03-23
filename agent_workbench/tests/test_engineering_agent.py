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
    str((Path(tempfile.gettempdir()) / "ludens_flow_tests" / "test_engineering_agent").resolve()),
)

import ludens_flow.state as st
from ludens_flow.agents.engineering_agent import EngineeringAgent


class EngineeringAgentPresetTests(unittest.TestCase):
    def setUp(self):
        st.init_workspace()

    def test_preset_selection_is_persisted_and_recoverable_from_history(self):
        agent = EngineeringAgent()
        agent._call = lambda *args, **kwargs: "mock reply"

        state = st.init_state()

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


if __name__ == "__main__":
    unittest.main()
