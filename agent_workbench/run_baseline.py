from __future__ import annotations
from pathlib import Path
import os
import tempfile

REPO_ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = REPO_ROOT / "artifacts"

def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), prefix=path.name, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.remove(tmp_path)
        except Exception:
            pass
        raise

def main() -> None:
    # 固定路径：按你们仓库约定的 artifacts 子目录写入
    gdd_path = ARTIFACTS / "gdd" / "GDD.md"
    pm_path = ARTIFACTS / "pm" / "PROJECT_PLAN.md"
    impl_path = ARTIFACTS / "coding" / "IMPLEMENTATION_PLAN.md"
    review_path = ARTIFACTS / "review" / "REVIEW_REPORT.md"
    status_path = REPO_ROOT / "STATUS.md"

    # 先写“能跑通”的占位内容（后面替换为真实Agent输出）
    atomic_write(
        gdd_path,
        "# GDD (Baseline Placeholder)\n\n"
        "## Pitch\n一个最小可跑通的baseline：先生成工件，后接入Agent。\n\n"
        "## Core Loop\n- 进入关卡\n- 完成目标\n- 结算\n",
    )

    atomic_write(
        pm_path,
        "# Project Plan (Baseline Placeholder)\n\n"
        "## Milestones\n- W1: baseline pipeline 跑通并产出工件\n- W2: JSON schema + 校验 + 重试\n",
    )

    atomic_write(
        impl_path,
        "# Implementation Plan (Baseline Placeholder)\n\n"
        "## Steps\n1. 固定路径落盘\n2. 线性pipeline: design -> pm -> engineering -> review\n3. 更新 STATUS.md\n",
    )

    atomic_write(
        review_path,
        "# Review Report (Baseline Placeholder)\n\n"
        "## Verdict\nPASS (placeholder)\n\n"
        "## Notes\n- 目前为占位版本，后续接入Agent输出与校验。\n",
    )

    atomic_write(status_path, "last_success_stage=review\n")

    print("✅ Baseline artifacts generated:")
    print(f"- {gdd_path.relative_to(REPO_ROOT)}")
    print(f"- {pm_path.relative_to(REPO_ROOT)}")
    print(f"- {impl_path.relative_to(REPO_ROOT)}")
    print(f"- {review_path.relative_to(REPO_ROOT)}")
    print(f"- {status_path.relative_to(REPO_ROOT)}")

if __name__ == "__main__":
    main()
