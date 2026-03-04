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
    str((Path(tempfile.gettempdir()) / "ludens_flow_tests" / "test_freeze").resolve()),
)

from ludens_flow.state import init_workspace, load_state, save_state
from ludens_flow.artifacts import write_artifact, write_dev_note, write_patch, artifact_exists

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

def run_tests():
    logger.info("Initializing Workspace and State...")
    init_workspace()
    state = load_state()

    logger.info("\n--- 测试 1: 进入 DEV_COACHING，开启 Artifact Freeze ---")
    state.phase = "DEV_COACHING"
    state.artifact_frozen = True
    save_state(state)
    logger.info("状态已冻结 (artifact_frozen = True)")

    logger.info("\n--- 测试 2: 冻结期间尝试修改 GDD (预期被拦截) ---")
    try:
        write_artifact("GDD", "This should fail", reason="Try hack frozen state", actor="DesignAgent", state=state)
        logger.error("❌ 拦截失败！冻结期依然修改了 canonical 文件！")
    except PermissionError as e:
        logger.info(f"✅ 成功拦截冻结期写入保护. 异常详情: {str(e)}")

    logger.info("\n--- 测试 3: 冻结期间写入 dev_note (预期成功) ---")
    try:
        p1 = write_dev_note("DECISIONS", "Decision 001: 考虑到开发周期，将关卡数量从 6 削减为 3。")
        logger.info(f"✅ 持续开发笔记追加成功: {p1}")
    except Exception as e:
        logger.error(f"❌ 追加笔记失败: {e}")

    logger.info("\n--- 测试 4: 冻结期间写入 Patch (预期成功) ---")
    try:
        p2 = write_patch("0001", "This patch proposes changes to the UI scheme without touching implementation_plan.md directly.")
        logger.info(f"✅ 补丁提交通道写入成功: {p2}")
    except Exception as e:
        logger.error(f"❌ 补丁写入失败: {e}")

if __name__ == "__main__":
    run_tests()
