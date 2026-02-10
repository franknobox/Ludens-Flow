from __future__ import annotations
from pathlib import Path
import os
import tempfile

from dotenv import load_dotenv
from llm import load_config, generate

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
    load_dotenv()
    cfg = load_config()

    # baseline：先写死一个需求，确保跑通；后续再改成命令行参数
    user_request = (
        "基于Unity6引擎，我希望制作一款赛博朋克题材的2D俯视角关卡制游戏，核心是暗杀与送货；"
        "强调潜行、路线规划、轻量战斗；每关有不同目标与撤离点。"
    )

    gdd_path = ARTIFACTS / "gdd" / "GDD.md"
    pm_path = ARTIFACTS / "pm" / "PROJECT_PLAN.md"
    impl_path = ARTIFACTS / "coding" / "IMPLEMENTATION_PLAN.md"
    review_path = ARTIFACTS / "review" / "REVIEW_REPORT.md"
    status_path = REPO_ROOT / "STATUS.md"

    gdd = generate(
        system="你是游戏策划(Design Agent)。产出可落盘的GDD Markdown。不要输出多余解释。",
        user=f"用户需求：{user_request}\n\n请输出Markdown，至少包含：概述/核心循环/关键系统/关卡结构/美术风格/不做什么(边界)。",
        cfg=cfg,
    )

    project_plan = generate(
        system="你是项目经理(PM Agent)。根据GDD制定项目计划Markdown。不要输出多余解释。",
        user=f"下面是GDD：\n{gdd}\n\n请输出Markdown，至少包含：里程碑(W1-W6)/任务拆分/角色分工建议/风险与缓解。",
        cfg=cfg,
    )

    impl_plan = generate(
        system="你是工程负责人(Engineering Agent)。根据GDD与项目计划输出实现计划Markdown。不要输出多余解释。",
        user=f"GDD：\n{gdd}\n\n项目计划：\n{project_plan}\n\n请输出Markdown，至少包含：目录结构建议/模块划分/关键接口/实现顺序/可测试点。",
        cfg=cfg,
    )

    review_report = generate(
        system="你是验收审查(Review Agent)。对工件给出评审报告Markdown。不要输出多余解释。",
        user=(
            "请评审以下工件，给出：Verdict(PASS/FAIL)、阻塞问题、非阻塞建议、下一步行动清单。\n\n"
            f"GDD：\n{gdd}\n\n项目计划：\n{project_plan}\n\n实现计划：\n{impl_plan}\n"
        ),
        cfg=cfg,
    )

    atomic_write(gdd_path, gdd + "\n")
    atomic_write(pm_path, project_plan + "\n")
    atomic_write(impl_path, impl_plan + "\n")
    atomic_write(review_path, review_report + "\n")
    atomic_write(status_path, "last_success_stage=review\n")

    print("✅ llm baseline artifacts generated:")
    print(f"- {gdd_path.relative_to(REPO_ROOT)}")
    print(f"- {pm_path.relative_to(REPO_ROOT)}")
    print(f"- {impl_path.relative_to(REPO_ROOT)}")
    print(f"- {review_path.relative_to(REPO_ROOT)}")
    print(f"- {status_path.relative_to(REPO_ROOT)}")
    print(f"provider={cfg.provider} model={cfg.model} base_url={cfg.base_url}")

if __name__ == "__main__":
    main()
