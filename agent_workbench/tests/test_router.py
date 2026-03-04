import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "src"))

import logging
import os
import tempfile
os.chdir(_ROOT)
os.environ.setdefault(
    "LUDENS_WORKSPACE_DIR",
    str((Path(tempfile.gettempdir()) / "ludens_flow_tests" / "test_router").resolve()),
)

from ludens_flow.state import init_state, save_state
from ludens_flow.router import route, Phase

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

def run_tests():
    # 使用全新内存状态，避免磁盘 state 污染
    state = init_state()
    save_state(state)  # 写盘确保 WorkspaceDir 及日志目录存在
    
    logger.info("--- 1. Testing GDD_DISCUSS -> GDD_COMMIT ---")
    state.phase = Phase.GDD_DISCUSS.value
    next_phase, explanation, updates = route(state, "定稿")
    logger.info(f"Route: {state.phase} -> {next_phase} ({explanation})")
    assert next_phase == Phase.GDD_COMMIT.value, f"Expected GDD_COMMIT, got {next_phase}"
    state.phase = next_phase
    
    logger.info("--- 2. Testing GDD_COMMIT -> PM_DISCUSS (via last_event) ---")
    next_phase, explanation, updates = route(state, "", last_event="GDD_COMMITTED")
    logger.info(f"Route: {state.phase} -> {next_phase} ({explanation})")
    assert next_phase == Phase.PM_DISCUSS.value, f"Expected PM_DISCUSS, got {next_phase}"
    state.phase = next_phase

    logger.info("--- 3. Fast Forward to REVIEW ---")
    state.phase = Phase.REVIEW.value
    state.review_gate = {"status": "REQUEST_CHANGES", "targets": ["PM"]}
    next_phase, explanation, updates = route(state, "", last_event="REVIEW_DONE")
    logger.info(f"Route: {state.phase} -> {next_phase} ({explanation})")
    assert next_phase == Phase.POST_REVIEW_DECISION.value, f"Expected POST_REVIEW_DECISION, got {next_phase}"
    state.phase = next_phase

    logger.info("--- 4. POST_REVIEW_DECISION -> PM (option A with PM target) ---")
    state.iteration_count = 0
    state.review_gate = {"status": "REQUEST_CHANGES", "targets": ["PM"], "issues": []}
    # 使用单字母 "a" 精确触发 opt_a
    next_phase, explanation, updates = route(state, "a")
    logger.info(f"Route: {state.phase} -> {next_phase} ({explanation})")
    assert next_phase == Phase.PM_DISCUSS.value, f"Expected PM_DISCUSS, got {next_phase}"
    assert updates.get("iteration_count") == 1
    state.phase = next_phase

    logger.info("--- 5. POST_REVIEW_DECISION -> DEV_COACHING (option C) ---")
    state.phase = Phase.POST_REVIEW_DECISION.value
    # 单字母 "c" 精确触发 opt_c
    next_phase, explanation, updates = route(state, "c")
    logger.info(f"Route: {state.phase} -> {next_phase} ({explanation})")
    assert next_phase == Phase.DEV_COACHING.value, f"Expected DEV_COACHING, got {next_phase}"
    assert updates.get("artifact_frozen") is True

    logger.info("All manual router checks passed.")
    save_state(state)

if __name__ == "__main__":
    run_tests()
