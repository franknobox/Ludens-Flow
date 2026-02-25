import sys
from pathlib import Path
import logging

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from ludens_flow.state import init_workspace, load_state, save_state
from ludens_flow.router import route, Phase

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

def run_tests():
    init_workspace()
    state = load_state()
    # Reset state to GDD_DISCUSS for clean test
    state.phase = Phase.GDD_DISCUSS.value
    state.iteration_count = 0
    state.artifact_frozen = False
    
    logger.info("--- 1. Testing GDD_DISCUSS -> GDD_COMMIT ---")
    next_phase, explanation, updates = route(state, "好的，我确认一下，可以定稿了")
    logger.info(f"Route: {state.phase} -> {next_phase} ({explanation})")
    assert next_phase == Phase.GDD_COMMIT.value
    for k, v in updates.items():
        setattr(state, k, v)
    
    logger.info("--- 2. Testing COMMIT -> PM_DISCUSS ---")
    next_phase, explanation, updates = route(state, "", last_event="commit_done")
    logger.info(f"Route: {state.phase} -> {next_phase} ({explanation})")
    assert next_phase == Phase.PM_DISCUSS.value
    for k, v in updates.items():
        setattr(state, k, v)

    logger.info("--- 3. Fast Forward to REVIEW ---")
    state.phase = Phase.REVIEW.value
    state.review_gate = "REQUEST_CHANGES"
    next_phase, explanation, updates = route(state, "", last_event="review_done")
    logger.info(f"Route: {state.phase} -> {next_phase} ({explanation})")
    assert next_phase == Phase.POST_REVIEW_DECISION.value
    for k, v in updates.items():
        setattr(state, k, v)

    logger.info("--- 4. POST_REVIEW_DECISION -> USER OPTIONS (1 = revision) ---")
    next_phase, explanation, updates = route(state, "我选择 1，回流修改")
    logger.info(f"Route: {state.phase} -> {next_phase} ({explanation})")
    assert next_phase == Phase.GDD_DISCUSS.value
    assert updates.get("iteration_count", 0) > 0
    for k, v in updates.items():
        setattr(state, k, v)

    logger.info("--- 5. Fast Forward POST_REVIEW_DECISION -> USER OPTIONS (2 = jump to dev) ---")
    state.phase = Phase.POST_REVIEW_DECISION.value
    next_phase, explanation, updates = route(state, "不管审查建议了，直接跳过进入开发！")
    logger.info(f"Route: {state.phase} -> {next_phase} ({explanation})")
    assert next_phase == Phase.DEV_COACHING.value
    assert updates.get("artifact_frozen") is True
    for k, v in updates.items():
        setattr(state, k, v)

    logger.info("All manual router checks passed.")
    save_state(state)

if __name__ == "__main__":
    run_tests()
