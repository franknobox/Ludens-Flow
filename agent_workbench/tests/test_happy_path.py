import sys
from pathlib import Path
import logging

sys.path.insert(0, str(Path(__file__).resolve().parents[1])) 
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ludens_flow.graph import graph_step
from dotenv import load_dotenv

# 加载项目根目录的 .env 文件
load_dotenv(Path(__file__).resolve().parents[2] / ".env")
from ludens_flow.router import Phase
from ludens_flow.agents.base import BaseAgent

# 纯净版 Mock 生成器
def mock_call(self, prompt, cfg=None):
    prompt_low = prompt.lower()
    
    # 模拟各类 Discuss 时带有的提取数据
    if self.name == "DesignAgent" and ("json" in prompt_low or "update_json" in prompt_low or "状态更新指令" in prompt_low):
         return (
             "GDD Discuss Mock: 我觉得杀戮尖塔不错。\n"
             "<<STATE_UPDATE_JSON>>\n"
             "{\"core_loop\": \"打怪-掉落-组卡\", \"mvp_scope\": \"30层\", \"open_questions\": [], \"setting\": \"中世纪暗黑\"}\n"
             "<<END_STATE_UPDATE_JSON>>"
         )
    elif self.name == "PMAgent" and "json" in prompt_low:
         return "PM Discuss Mock\n```json\n{\"team_size\": 3}\n```"
    elif self.name == "EngineeringAgent" and "json" in prompt_low:
         return "Eng Discuss Mock\n```json\n{\"style_preset\": \"OOP\"}\n```"
    elif self.name == "ReviewAgent" and "json" in prompt_low:
         # 乖乖给通过的打分
         return "Review Commit Mock\n```json\n{\"status\": \"PASS\", \"targets\": [], \"score\": 95, \"issues\": []}\n```"
    return "Mocked Answer"

BaseAgent._call = mock_call

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def run_happy_path():
    logger.info("==========================================")
    logger.info("   Ludens Flow - Happy Path Acceptance    ")
    logger.info("==========================================\n")
    
    import shutil
    import os
    if os.path.exists("workspace/state.json"):
        os.remove("workspace/state.json")
    
    # 强制清理重新初始工作区，防污染
    import ludens_flow.state as st
    st.WORKSPACE_DIR = Path("workspace")
    st.init_workspace()
    state = st.load_state()

    assert state.phase == Phase.GDD_DISCUSS.value, "Initial phase must be GDD_DISCUSS"

    # --- 阶段 1：策划 GDD ---
    logger.info("[1] 正在进行 GDD 讨论与定稿...")
    state = graph_step(state, "我要做一个类似杀戮尖塔的游戏")
    state = graph_step(state, "2 定稿生成")
    state = graph_step(state, "")  # 触发 Agent 生成 Commit
    
    assert "gdd" in state.artifacts, "GDD failed to generate"
    assert state.phase == Phase.PM_DISCUSS.value, f"Failed to transition to PM, stopped at {state.phase}"

    # --- 阶段 2：项目 PM ---
    logger.info("[2] 正在进行 PM 讨论与定稿...")
    state = graph_step(state, "我们有 3 个人，开发两周")
    state = graph_step(state, "2 定稿生成")
    state = graph_step(state, "")  # 触发 Agent 生成 Commit
    
    assert "pm" in state.artifacts, "PM Plan failed to generate"
    assert state.phase == Phase.ENG_DISCUSS.value, f"Failed to transition to ENG, stopped at {state.phase}"

    # --- 阶段 3：工程 ENG ---
    logger.info("[3] 正在进行 ENG 讨论与定稿...")
    state = graph_step(state, "我们决定采用 A 预设，快速出个原型的 Demo跑起来！")
    state = graph_step(state, "2 定稿并生成")
    state = graph_step(state, "")  # 触发 Agent 提交并扭转
    
    assert "eng" in state.artifacts, "ENG Plan failed to generate"
    assert state.phase == Phase.REVIEW.value, f"Failed to transition to REVIEW, stopped at {state.phase}"

    # --- 阶段 4：审核 REVIEW ---
    logger.info("[4] 正在进行 REVIEW 审查与裁决...")
    state = graph_step(state, "")  # 触发 Review Agent
    assert "review" in state.artifacts, "REVIEW failed to generate"
    assert state.phase == Phase.POST_REVIEW_DECISION.value, f"Failed to transition to POST_REVIEW, stopped at {state.phase}"

    # --- 阶段 5：用户最终拍板 ---
    logger.info("[5] 审查全线 PASS，用户同意终稿...")
    state = graph_step(state, "c")  # 选择 Option C: 强行通过进入研发
    assert state.phase == Phase.DEV_COACHING.value, f"Failed to transition to DEV_COACHING, stopped at {state.phase}"
    assert getattr(state, "artifact_frozen", False) == True, "Artifacts should be frozen"

    logger.info("\n✅ Happy Path 全链路绿灯通关！没有任何阻塞！")

if __name__ == "__main__":
    run_happy_path()
