import sys
from pathlib import Path
import logging

sys.path.insert(0, str(Path(__file__).resolve().parents[1])) 
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ludens_flow.state import init_workspace, load_state, save_state
from ludens_flow.agents.orchestrator import execute_step
from ludens_flow.router import Phase
from ludens_flow.agents.base import BaseAgent

# Mock 生成器避免真实调用 LLM
def mock_call(self, prompt, cfg=None):
    prompt_low = prompt.lower()
    if self.name == "EngineeringAgent" and "implementation_plan.md" in prompt_low:
         return "Eng Commit Mock!"
    elif self.name == "PMAgent" and "project_plan.md" in prompt_low:
         return "PM Commit Mock!"
    elif self.name == "DesignAgent" and "gdd(game design document)" in prompt_low:
         return "GDD Commit Mock!"
         
    if self.name == "DesignAgent" and "json" in prompt_low:
         return "GDD Discuss Mock\n```json\n{\"core_loop\": \"kill-loot\"}\n```"
    elif self.name == "PMAgent" and "json" in prompt_low:
         return "PM Discuss Mock\n```json\n{\"team_size\": 3}\n```"
    elif self.name == "EngineeringAgent" and "```json" in prompt_low:
         return "Eng Discuss Mock\n```json\n{\"style_preset\": \"OOP\"}\n```"
    elif self.name == "ReviewAgent" and "```json" in prompt_low:
         # Review Agent Gate
         return "Review Commit Mock\n```json\n{\"status\": \"BLOCK\", \"targets\": [\"ENG\"], \"score\": 60, \"issues\": []}\n```"
    return "Mocked Answer"

BaseAgent._call = mock_call

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def run_flow_test():
    init_workspace()
    
    # 强制重置一条干净的时间线，清除旧文件
    state = load_state()
    state.phase = Phase.GDD_DISCUSS.value
    state.iteration_count = 0
    state.drafts = {"gdd": {}, "pm": {}, "eng": {}}
    from ludens_flow.state import ArtifactMeta
    state.artifacts = {
        "gdd": ArtifactMeta(path="", owner="DesignAgent"),
        "pm": ArtifactMeta(path="", owner="PMAgent"),
        "eng": ArtifactMeta(path="", owner="EngineeringAgent"),
        "review": ArtifactMeta(path="", owner="ReviewAgent")
    }
    state.decisions = []
    state.review_gate = None
    state.artifact_frozen = False
    state.last_event = None
    save_state(state)
    
    logger.info("\n=== 验收场景 1: GDD_DISCUSS 自由对话 ===")
    msg, state = execute_step(state, "我想做一款暗黑like的刷宝ARPG游戏，主打高自由度BD构建。")
    logger.info(f"-> 阶段: {state.phase}")
    logger.info(f"-> Draft: {state.drafts.get('gdd')}")
    assert state.phase == Phase.GDD_DISCUSS.value
    assert "core_loop" in state.drafts["gdd"]

    logger.info("\n=== 验收场景 2: 向 GDD_COMMIT 跳转并落盘 ===")
    # 用户给出确认并选择 2
    msg, state = execute_step(state, "2 定稿生成")
    logger.info(f"-> 切换阶段至: {state.phase}")
    msg, state = execute_step(state, "")
    logger.info(f"-> 执行 Commit 后阶段: {state.phase}")
    assert "gdd" in state.artifacts, "gdd meta missing"
    assert state.artifacts["gdd"].version == 1, "gdd Version incorrect"
    assert state.phase == Phase.PM_DISCUSS.value, f"Automated transition failed, currently at {state.phase}"

    logger.info("\n=== 验收场景 3: PM_DISCUSS 后敲定 PROJECT PLAN ===")
    _, state = execute_step(state, "团队有3个人，全职开发半年")
    assert state.phase == Phase.PM_DISCUSS.value
    
    msg, state = execute_step(state, "2")
    msg, state = execute_step(state, "")
    logger.info(f"-> 阶段: {state.phase}")
    assert "pm" in state.artifacts
    assert state.phase == Phase.ENG_DISCUSS.value

    logger.info("\n=== 验收场景 4: ENG_DISCUSS 选择 preset 并确认实现方案 ===")
    # 发送包含 preset 的指令
    _, state = execute_step(state, "我们选用 OOP 的预设风格，使用 Unity 引擎。")
    assert state.style_preset == "OOP", f"Preset extraction failed, got {state.style_preset}"
    
    msg, state = execute_step(state, "2 定稿生成")
    # 模拟 EngineeringAgent 执行并提交，Router 被激活顺滑流转至 REVIEW
    msg, state = execute_step(state, "")
    logger.info(f"-> 阶段: {state.phase}")
    assert "eng" in state.artifacts
    assert state.phase == Phase.REVIEW.value

    logger.info("\n=== 验收场景 5: REVIEW 闭环打分及门神解析 ===")
    # 让 Review Agent 运行发问并挂载 Gate
    msg, state = execute_step(state, "")
    logger.info(f"-> 阶段: {state.phase}")
    assert "review" in state.artifacts
    assert state.review_gate is not None
    assert "status" in state.review_gate
    assert state.phase == Phase.POST_REVIEW_DECISION.value
    
    logger.info("\n✅ Step 4 (Agent x Router x Artifacts) 综合联调全链路测试通过！")

if __name__ == "__main__":
    run_flow_test()
