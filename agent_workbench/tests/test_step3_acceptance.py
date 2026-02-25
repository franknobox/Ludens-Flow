import sys
from pathlib import Path
import logging

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ludens_flow.state import init_state, LudensState
from ludens_flow.router import route, Phase

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def verify_scenario(name: str, state: LudensState, user_input: str, last_event: str, 
                    expected_phase: str, checker=None):
    logger.info(f"\n[验证场景] {name}")
    next_phase, explanation, updates = route(state, user_input, last_event)
    
    # Apply updates
    for k, v in updates.items():
        setattr(state, k, v)
        
    logger.info(f"   => 期望前往: {expected_phase} | 实际达到: {state.phase}")
    logger.info(f"   => 原因: {explanation}")
    assert state.phase == expected_phase, f"Fail: Expected {expected_phase}, got {state.phase}"
    
    if checker:
        checker(state, updates)


def run_acceptance_tests():
    logger.info("=== 开始 Step 3 核心交付验收测试 ===")
    
    # 场景 1: 启动无 state 或 phase
    state = init_state()
    # 按照规定，空 phase 或未知 phase，直接路由到 GDD_DISCUSS
    state.phase = ""
    verify_scenario(
        "启动无对应 phase：进入 GDD_DISCUSS",
        state, "随便啥", None,
        Phase.GDD_DISCUSS.value
    )
    
    # 场景 2: 在 GDD_DISCUSS 输入 2 -> 进入 GDD_COMMIT
    state.phase = Phase.GDD_DISCUSS.value
    verify_scenario(
        "在 GDD_DISCUSS 输入 2：进入 GDD_COMMIT",
        state, "2", None,
        Phase.GDD_COMMIT.value
    )
    
    # 场景 3: 完成 GDD_COMMIT（写 last_event）-> 自动去 PM_DISCUSS
    state.phase = Phase.GDD_COMMIT.value
    verify_scenario(
        "完成 GDD_COMMIT（含 last_event）：自动去 PM_DISCUSS",
        state, "", "GDD_COMMITTED",
        Phase.PM_DISCUSS.value
    )
    
    # 场景 4: 一路走到 REVIEW，填入 gate=BLOCK targets=[PM] -> POST_REVIEW_DECISION
    state.phase = Phase.REVIEW.value
    state.review_gate = {"status": "BLOCK", "targets": ["PM"]}
    verify_scenario(
        "在 REVIEW 完结，遭遇退回审查：进入 POST_REVIEW_DECISION",
        state, "", "REVIEW_DONE",
        Phase.POST_REVIEW_DECISION.value
    )
    
    # 场景 5: 在 POST_REVIEW_DECISION 输入 A -> 回流到 PM_DISCUSS，iteration_count+1
    state.phase = Phase.POST_REVIEW_DECISION.value
    state.iteration_count = 0 
    def check_iter(s, upd):
        assert upd.get("iteration_count") == 1, "iteration_count should +1"
        
    verify_scenario(
        "在 POST_REVIEW_DECISION 输入 A：回流到 PM_DISCUSS 因为 target 是 PM",
        state, "A", None,
        Phase.PM_DISCUSS.value,
        check_iter
    )
    
    # 场景 6: 撤回到 POST_REVIEW_DECISION，选择 C 进入 DEV_COACHING -> 验证双保险拦截
    state.phase = Phase.POST_REVIEW_DECISION.value
    def check_dev(s, upd):
        assert upd.get("artifact_frozen") is True, "Must freeze artifacts in DEV_COACHING"
        
    verify_scenario(
        "在 POST_REVIEW_DECISION 选择 C：进入 DEV_COACHING 冻结",
        state, "C", None,
        Phase.DEV_COACHING.value,
        check_dev
    )
    
    # 验证 DEV_COACHING 内输入 2 不跳回 commit 而是原地解封提醒
    state.phase = Phase.DEV_COACHING.value
    verify_scenario(
        "在 DEV_COACHING 输入 2/commit ：不应进入 commit 而是保持原地",
        state, "2 定稿", None,
        Phase.DEV_COACHING.value
    )

    logger.info("\n✅ Step 3 所有验收标准全部通过！")

if __name__ == "__main__":
    run_acceptance_tests()
