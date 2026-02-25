import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1])) 
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import ludens_flow.state as st
from ludens_flow.graph import graph_step

st.WORKSPACE_DIR = Path("workspace")
st.init_workspace()
state = st.load_state()
state.phase = 'GDD_COMMIT'

from ludens_flow.agents.base import BaseAgent, AgentResult, CommitSpec

def mock_call(self, prompt, cfg=None):
    return AgentResult(assistant_message="", commit=CommitSpec(artifact_name="GDD", content="mock!\n", reason="test"), state_updates={})

BaseAgent._call = mock_call

try:
    state = graph_step(state, '2 定稿生成')
    print("Graph Step Success. Phase:", state.phase)
except Exception as e:
    import traceback
    traceback.print_exc()
