from __future__ import annotations
from pathlib import Path
import os
import sys
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

    # 从终端读取需求：有命令行参数则直接用，否则交互式输入
    if len(sys.argv) > 1:
        user_request = " ".join(sys.argv[1:])
    else:
        print("请输入你的游戏开发需求：")
        user_request = input("> ").strip()
        if not user_request:
            print("❌ 需求不能为空，已退出。")
            sys.exit(1)

    gdd_path = ARTIFACTS / "gdd" / "GDD.md"
    pm_path = ARTIFACTS / "pm" / "PROJECT_PLAN.md"
    impl_path = ARTIFACTS / "coding" / "IMPLEMENTATION_PLAN.md"
    review_path = ARTIFACTS / "review" / "REVIEW_REPORT.md"
    status_path = REPO_ROOT / "STATUS.md"

    print("[1/4] 🎮 Design Agent 正在生成 GDD...")
    gdd = generate(
        system="你是游戏策划(Design Agent)。产出可落盘的GDD Markdown。不要输出多余解释。",
        user=f"用户需求：{user_request}\n\n请输出Markdown，至少包含：概述/核心循环/关键系统/关卡结构/美术风格/不做什么(边界)。",
        cfg=cfg,
    )
    print("      ✓ GDD 生成完成")

    print("[2/4] 📋 PM Agent 正在生成项目计划...")
    project_plan = generate(
        system="你是项目经理(PM Agent)。根据GDD制定项目计划Markdown。不要输出多余解释。",
        user=f"下面是GDD：\n{gdd}\n\n请输出Markdown，至少包含：里程碑(W1-W6)/任务拆分/角色分工建议/风险与缓解。",
        cfg=cfg,
    )
    print("      ✓ 项目计划生成完成")

    print("[3/4] 🔧 Engineering Agent 正在生成实现计划...")
    impl_plan = generate(
        system="你是工程负责人(Engineering Agent)。根据GDD与项目计划输出实现计划Markdown。不要输出多余解释。",
        user=f"GDD：\n{gdd}\n\n项目计划：\n{project_plan}\n\n请输出Markdown，至少包含：目录结构建议/模块划分/关键接口/实现顺序/可测试点。",
        cfg=cfg,
    )
    print("      ✓ 实现计划生成完成")

    print("[4/4] 🔍 Review Agent 正在评审所有产物...")
    review_report = generate(
        system="你是验收审查(Review Agent)。对工件给出评审报告Markdown。不要输出多余解释。",
        user=(
            "请评审以下工件，给出：Verdict(PASS/FAIL)、阻塞问题、非阻塞建议、下一步行动清单。\n\n"
            f"GDD：\n{gdd}\n\n项目计划：\n{project_plan}\n\n实现计划：\n{impl_plan}\n"
        ),
        cfg=cfg,
    )
    print("      ✓ 评审报告生成完成")

    print("\n💾 正在写入产物文件...")
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
