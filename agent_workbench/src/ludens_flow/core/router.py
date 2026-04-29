"""
文件功能：流程路由器，根据状态与用户输入决定下一阶段与动作。
核心内容：统一维护 phase 枚举、显式动作识别和默认流转规则。
核心内容：输出可解释的路由原因，供 graph 与前端动作面板复用。
"""

import logging
import re
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from ludens_flow.core.paths import get_logs_dir
from ludens_flow.core.state import LudensState

logger = logging.getLogger(__name__)


class Phase(str, Enum):
    GDD_DISCUSS = "GDD_DISCUSS"
    GDD_COMMIT = "GDD_COMMIT"
    PM_DISCUSS = "PM_DISCUSS"
    PM_COMMIT = "PM_COMMIT"
    ENG_DISCUSS = "ENG_DISCUSS"
    ENG_COMMIT = "ENG_COMMIT"
    REVIEW = "REVIEW"
    POST_REVIEW_DECISION = "POST_REVIEW_DECISION"
    DEV_COACHING = "DEV_COACHING"


PHASE_ACTIONS: Dict[str, List[Dict[str, str]]] = {
    Phase.GDD_DISCUSS.value: [
        {
            "id": "gdd_commit",
            "label": "定稿并生成 GDD",
            "description": "结束当前讨论并生成 GDD 文档。",
        }
    ],
    Phase.PM_DISCUSS.value: [
        {
            "id": "pm_commit",
            "label": "定稿并生成 PROJECT_PLAN",
            "description": "结束 PM 讨论并生成项目计划。",
        },
        {
            "id": "pm_back",
            "label": "回退到 GDD",
            "description": "返回 GDD 阶段继续澄清需求。",
        },
    ],
    Phase.ENG_DISCUSS.value: [
        {
            "id": "eng_commit",
            "label": "定稿并生成 IMPLEMENTATION_PLAN",
            "description": "结束工程讨论并生成实施计划。",
        },
        {
            "id": "eng_back",
            "label": "回退到 PM",
            "description": "返回 PM 阶段调整排期和范围。",
        },
    ],
    Phase.POST_REVIEW_DECISION.value: [
        {
            "id": "review_option_a",
            "label": "A: 接受建议并回流",
            "description": "按评审 targets 回流到对应阶段。",
        },
        {
            "id": "review_option_b",
            "label": "B: 仅修 BLOCK/MAJOR",
            "description": "仅针对严重问题回流。",
        },
        {
            "id": "review_option_c",
            "label": "C: 强制进入 DEV_COACHING",
            "description": "忽略回流，直接进入开发辅导。",
        },
    ],
}


ACTION_USER_TEXT: Dict[str, str] = {
    "gdd_commit": "[ACTION] 定稿并生成 GDD",
    "pm_commit": "[ACTION] 定稿并生成 PROJECT_PLAN",
    "pm_back": "[ACTION] 回退到 GDD",
    "eng_commit": "[ACTION] 定稿并生成 IMPLEMENTATION_PLAN",
    "eng_back": "[ACTION] 回退到 PM",
    "review_option_a": "[ACTION] A: 接受建议并回流",
    "review_option_b": "[ACTION] B: 仅修 BLOCK/MAJOR",
    "review_option_c": "[ACTION] C: 强制进入 DEV_COACHING",
}


def get_phase_actions(phase: Optional[str]) -> List[Dict[str, str]]:
    resolved_phase = phase or Phase.GDD_DISCUSS.value
    return [dict(item) for item in PHASE_ACTIONS.get(resolved_phase, [])]


def get_available_actions(state: LudensState) -> List[Dict[str, str]]:
    return get_phase_actions(getattr(state, "phase", None))


def action_user_input(action_id: str) -> str:
    return ACTION_USER_TEXT.get(action_id, f"[ACTION] {action_id}")


def _is_action_allowed(phase: str, action_id: Optional[str]) -> bool:
    if not action_id:
        return False
    allowed_ids = {item["id"] for item in get_phase_actions(phase)}
    return action_id in allowed_ids


def _log_route(
    old_phase: str,
    new_phase: str,
    explanation: str,
    user_input: str = "",
    state: Optional[LudensState] = None,
) -> None:
    """写入符合检索标准的格式化路由决策日志"""
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    # 获取迭代状态信息
    iter_info = "iter=0/6"
    gate_info = ""
    art_info = ""

    if state:
        iter_info = f"iter={state.iteration_count}/{state.max_iterations}"

        # 获取最新的 Review Gate 结论
        if state.review_gate and isinstance(state.review_gate, dict):
            status = state.review_gate.get("status", "")
            if status:
                gate_info = f"gate_status={status} "

        # 简单记录四个工件的 version (如果有)
        arts = state.artifacts
        if arts:
            v_gdd = arts.get("gdd").version if "gdd" in arts else 0
            v_pm = arts.get("pm").version if "pm" in arts else 0
            v_eng = arts.get("eng").version if "eng" in arts else 0
            art_info = f"v_gdd={v_gdd} v_pm={v_pm} v_eng={v_eng}"

    # 清理一下用户输入避免破行
    safe_input = user_input.replace("\n", " ").strip()
    user_choice = f'choice="{safe_input}"' if safe_input else 'choice=""'

    # 拼装最终单行日志
    log_line = (
        f"{timestamp} {iter_info} {old_phase}->{new_phase} "
        f'{user_choice} {gate_info}reason="{explanation}" {art_info}\n'
    )

    router_log_file = (
        get_logs_dir(getattr(state, "project_id", None) if state else None)
        / "router.log"
    )
    router_log_file.parent.mkdir(parents=True, exist_ok=True)
    with open(router_log_file, "a", encoding="utf-8") as f:
        f.write(log_line)

    logger.info(f"Router Decision: {old_phase} -> {new_phase} ({explanation})")


def _get_backflow_phase(targets: List[str]) -> str:
    """按固定优先级决定回流到哪一步: GDD > PM > ENG"""
    targets_upper = [t.upper() for t in targets]
    if "GDD" in targets_upper:
        return Phase.GDD_DISCUSS.value
    if "PM" in targets_upper:
        return Phase.PM_DISCUSS.value
    if "ENG" in targets_upper:
        return Phase.ENG_DISCUSS.value
    return Phase.GDD_DISCUSS.value  # 默认回退到最初游


def route(
    state: LudensState,
    user_input: str,
    last_event: Optional[str] = None,
    explicit_action: Optional[str] = None,
) -> Tuple[str, str, Dict[str, Any]]:
    """
    中央路由逻辑 (State Machine)

    Args:
        state: 当前状态
        user_input: 用户的原始输入，用于提取命令选项
        last_event: 前置事件（用于 COMMIT/REVIEW 等无人值守环节后自动跳转）
    """
    # 兼容没有初始化的状况
    current_phase = state.phase or Phase.GDD_DISCUSS.value

    # Extract text content safely if user_input is a multimodal list
    if isinstance(user_input, list):
        text_parts = [
            item.get("text", "") for item in user_input if item.get("type") == "text"
        ]
        user_text = " ".join(text_parts).strip().lower()
    else:
        user_text = str(user_input).strip().lower()

    updates: Dict[str, Any] = {}
    if not state.phase:
        updates["phase"] = current_phase

    # --- 防无限回路与死锁拦截 ---
    if (
        state.iteration_count > state.max_iterations
        and current_phase != Phase.DEV_COACHING.value
    ):
        explanation = (
            f"Reached iteration limit ({state.max_iterations}). Forcing DEV_COACHING."
        )
        _log_route(
            current_phase, Phase.DEV_COACHING.value, explanation, user_text, state
        )
        return (
            Phase.DEV_COACHING.value,
            explanation,
            {"phase": Phase.DEV_COACHING.value, "artifact_frozen": True},
        )

    next_phase = current_phase
    explanation = "Stay in current phase by default."

    # --- 统一解析工作流动作（仅接受显式选项，不做自由文本意图猜测） ---
    action = str(explicit_action or "").strip().lower()
    if action and not _is_action_allowed(current_phase, action):
        action = ""

    wants_commit = action in {"gdd_commit", "pm_commit", "eng_commit"}
    wants_back = action in {"pm_back", "eng_back"}

    opt_a = action == "review_option_a"
    opt_b = action == "review_option_b"
    opt_c = action == "review_option_c"

    wants_unfreeze = any(
        k in user_text for k in ["解冻", "修改工件", "重新评审", "开启新迭代"]
    )

    # 如果已经在 DEV_COACHING，做第一优先级的冰封判断 (Step 3.4 冻结拦截)
    if current_phase == Phase.DEV_COACHING.value:
        if wants_commit and not wants_unfreeze:
            explanation = "User attempted to commit during DEV_COACHING (Frozen). Suggesting unfreeze first."
            _log_route(current_phase, next_phase, explanation, user_text, state)
            return (
                next_phase,
                explanation,
                {"artifact_frozen": True},
            )  # 拦截跳转，原路返回提示

        if wants_unfreeze:
            next_phase = Phase.ENG_DISCUSS.value  # 默认解冻回最近的一步，也可后续做动态
            explanation = (
                "User requested unfreeze. Opening new iteration at ENG_DISCUSS."
            )
            updates["artifact_frozen"] = False
            updates["iteration_count"] = state.iteration_count + 1
        else:
            explanation = "Continuing DEV_COACHING."
            updates["artifact_frozen"] = True

        _log_route(current_phase, next_phase, explanation, user_text, state)
        if next_phase != current_phase:
            updates["phase"] = next_phase
        return next_phase, explanation, updates

    # --- 正常流转区 ---
    if current_phase == Phase.GDD_DISCUSS.value:
        if wants_commit:
            next_phase = Phase.GDD_COMMIT.value
            explanation = "User chose to commit GDD."
        else:
            explanation = "Continuing GDD discussion."

    elif current_phase == Phase.GDD_COMMIT.value:
        if last_event == "GDD_COMMITTED":
            next_phase = Phase.PM_DISCUSS.value
            explanation = "GDD committed automatically, moving to PM discussion."

    elif current_phase == Phase.PM_DISCUSS.value:
        if wants_commit:
            next_phase = Phase.PM_COMMIT.value
            explanation = "User chose to commit PM plan."
        elif wants_back:
            next_phase = Phase.GDD_DISCUSS.value
            explanation = "Flowing back to GDD discussion."

    elif current_phase == Phase.PM_COMMIT.value:
        if last_event == "PM_COMMITTED":
            next_phase = Phase.ENG_DISCUSS.value
            explanation = "PM committed automatically, moving to ENG discussion."

    elif current_phase == Phase.ENG_DISCUSS.value:
        if wants_commit:
            next_phase = Phase.ENG_COMMIT.value
            explanation = "User chose to commit Engineering plan."
        elif wants_back:
            next_phase = Phase.PM_DISCUSS.value
            explanation = "Flowing back to PM discussion."

    elif current_phase == Phase.ENG_COMMIT.value:
        # 当工程实现方案提交后，自动进入内部审查期
        if last_event == "ENG_COMMITTED":
            next_phase = Phase.REVIEW.value
            explanation = "ENG committed automatically, moving to internal Review."

    elif current_phase == Phase.REVIEW.value:
        if last_event == "REVIEW_DONE":
            # 一步到位：如果用户在看到 ReviewAgent 的 A/B/C 选项后已经做出选择，直接执行
            gate = state.review_gate or {}
            gate_status = gate.get("status", "PASS")
            gate_targets = gate.get("targets", [])
            gate_issues = gate.get("issues", [])

            if opt_a:
                if not gate_targets:
                    next_phase = Phase.GDD_DISCUSS.value
                else:
                    next_phase = _get_backflow_phase(gate_targets)
                explanation = f"User Option A: Flowing back to target ({next_phase})."
                updates["iteration_count"] = state.iteration_count + 1
            elif opt_b:
                serious_targets = [
                    issue.get("target", "GDD")
                    for issue in gate_issues
                    if issue.get("severity", "").upper() in ("BLOCK", "MAJOR")
                ]
                if not serious_targets:
                    explanation = (
                        "Option B: No BLOCK/MAJOR issues. Flowing to DEV_COACHING."
                    )
                    next_phase = Phase.DEV_COACHING.value
                    updates["artifact_frozen"] = True
                else:
                    next_phase = _get_backflow_phase(serious_targets)
                    explanation = f"User Option B: Flowing back to major issues target ({next_phase})."
                    updates["iteration_count"] = state.iteration_count + 1
            elif opt_c or gate_status == "PASS":
                next_phase = Phase.DEV_COACHING.value
                explanation = "User Option C or PASS: Entering DEV_COACHING and freezing artifacts."
                updates["artifact_frozen"] = True
            else:
                # 用户未做有效选择，降落到 POST_REVIEW_DECISION 等待
                next_phase = Phase.POST_REVIEW_DECISION.value
                explanation = "Review completed, awaiting user decision (A/B/C)."

    elif current_phase == Phase.POST_REVIEW_DECISION.value:
        # Step 3.3 核心流转机制
        gate = state.review_gate or {}
        gate_status = gate.get("status", "PASS")
        gate_targets = gate.get("targets", [])
        gate_issues = gate.get("issues", [])

        if opt_a:
            if not gate_targets:
                next_phase = Phase.GDD_DISCUSS.value
            else:
                next_phase = _get_backflow_phase(gate_targets)
            explanation = f"User Option A: Flowing back to target ({next_phase})."
            updates["iteration_count"] = state.iteration_count + 1
        elif opt_b:
            serious_targets = [
                issue.get("target", "GDD")
                for issue in gate_issues
                if issue.get("severity", "").upper() in ("BLOCK", "MAJOR")
            ]
            if not serious_targets:
                explanation = "Option B clicked but no BLOCK/MAJOR issues found. Flowing to DEV_COACHING."
                next_phase = Phase.DEV_COACHING.value
                updates["artifact_frozen"] = True
            else:
                next_phase = _get_backflow_phase(serious_targets)
                explanation = f"User Option B: Flowing back to major issues target ({next_phase})."
                updates["iteration_count"] = state.iteration_count + 1
        elif opt_c or gate_status == "PASS":
            next_phase = Phase.DEV_COACHING.value
            explanation = (
                "User Option C or PASS: Entering DEV_COACHING and freezing artifacts."
            )
            updates["artifact_frozen"] = True
        else:
            explanation = "Waiting for user decision on Review results."

    else:
        explanation = (
            f"Unknown phase '{current_phase}'. Forcing to GDD_DISCUSS to recover."
        )
        next_phase = Phase.GDD_DISCUSS.value

    # --- 统一更新机制 ---
    _log_route(current_phase, next_phase, explanation, user_text, state)
    if next_phase != current_phase:
        updates["phase"] = next_phase

    return next_phase, explanation, updates


@dataclass
class RouterResult:
    next_phase: str
    explanation: str


def ludens_router_logic(state: LudensState, user_input: str) -> RouterResult:
    """
    给 graph.py 节点引擎提供的高级封装接口：
    不仅返回明确定义的 RouterResult 实体，同时由于 Router 在执行判断如 POST_REVIEW_DECISION 回流时，
    会发生 `iteration_count += 1` 或开启冻结 `artifact_frozen = True` 的属性修改。
    通过这个接口可在此将原三元返回字典 updates 中的关键路由变量强制压入全局 state 实例。
    """
    last_event = getattr(state, "last_event", None)
    nxt, exp, ups = route(state, user_input, last_event)

    # 清理掉 last_event 表示已被消耗
    state.last_event = None

    # 应用关键状态机变量
    if "iteration_count" in ups:
        state.iteration_count = ups["iteration_count"]
    if "artifact_frozen" in ups:
        state.artifact_frozen = ups["artifact_frozen"]
        # 将这些更新后的底层值刷回图大盘，使得其它 Node 对冰封敏感

    return RouterResult(next_phase=nxt, explanation=exp)


def ludens_router_logic_with_action(
    state: LudensState, user_input: str, explicit_action: Optional[str] = None
) -> RouterResult:
    """支持显式 workflow action 的路由封装。"""
    last_event = getattr(state, "last_event", None)
    nxt, exp, ups = route(
        state,
        user_input,
        last_event,
        explicit_action=explicit_action,
    )

    state.last_event = None

    if "iteration_count" in ups:
        state.iteration_count = ups["iteration_count"]
    if "artifact_frozen" in ups:
        state.artifact_frozen = ups["artifact_frozen"]

    return RouterResult(next_phase=nxt, explanation=exp)
