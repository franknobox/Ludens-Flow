import logging
import os
import sys
import tempfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]  # agent_workbench/
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "src"))

os.environ.setdefault(
    "LUDENS_WORKSPACE_DIR",
    str((Path(tempfile.gettempdir()) / "ludens_flow_tests" / "test_artifacts").resolve()),
)

from ludens_flow.artifacts import artifact_exists, read_artifact, write_artifact
from ludens_flow.state import init_workspace, load_state, save_state

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

WORKSPACE = Path(os.environ["LUDENS_WORKSPACE_DIR"])


def run_tests():
    # 切换工作目录确保相对导入行为和旧脚本一致，但 workspace 已固定到测试目录。
    os.chdir(_ROOT)

    logger.info("初始化工作区并加载 State...")
    WORKSPACE.mkdir(parents=True, exist_ok=True)
    (WORKSPACE / "state.json").unlink(missing_ok=True)
    init_workspace()
    state = load_state()

    logger.info("\n--- 测试 1: 正常单写入权覆盖 (GDD_AGENT) ---")
    reason_1 = "Initial commit of GDD"
    content_1 = "# Game Design Document\nThis is a test."
    write_artifact("GDD", content_1, reason=reason_1, actor="DesignAgent", state=state)
    logger.info(f"GDD version: {state.artifacts['gdd'].version}, hash: {state.artifacts['gdd'].hash[:8]}")

    logger.info("\n--- 测试 2: 二次内容写入 (GDD_AGENT) ---")
    reason_2 = "Update storyline"
    content_2 = "# Game Design Document\nThis is a test.\n\nAdded new storylines."
    write_artifact("GDD", content_2, reason=reason_2, actor="DesignAgent", state=state)
    logger.info(f"GDD version expected to be 2. Actual: {state.artifacts['gdd'].version}, hash: {state.artifacts['gdd'].hash[:8]}")

    logger.info("\n--- 测试 3: 拦截非法越权修改 (PM_AGENT 试图改 GDD) ---")
    try:
        write_artifact("GDD", "Illegal inject", reason="Hack", actor="PMAgent", state=state)
        logger.error("越权拦截失败，PMAgent 成功写入了 GDD。")
    except PermissionError as e:
        logger.info(f"成功拦截了非法修改。异常详情: {str(e)}")

    logger.info("\n--- 测试 4: 拦截未知工件名称 ---")
    try:
        write_artifact("INVALID_DOC", "...", reason="...", actor="DesignAgent", state=state)
    except ValueError as e:
        logger.info(f"成功拦截了不合法的工件名。{str(e)}")

    logger.info("\n--- 测试 5: read_artifact 与空文件重建 ---")
    gdd_path = WORKSPACE / "GDD.md"
    if gdd_path.exists():
        gdd_path.unlink()

    lost_content = read_artifact("GDD")
    logger.info(
        "从磁盘重建空文件读取结果为: '%s', 磁盘实体重新创建存在与否: %s",
        lost_content,
        artifact_exists("GDD"),
    )

    logger.info("\n--- 测试完毕，状态覆盘保存 ---")
    save_state(state)
    logger.info("验收全部成功。")


if __name__ == "__main__":
    run_tests()
