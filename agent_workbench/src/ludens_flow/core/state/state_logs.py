"""
文件功能：状态子模块（state_logs.py），服务项目级状态持久化与演进。
核心内容：围绕状态读写、迁移、日志与项目工作区操作提供基础能力。
核心内容：与 graph/router 协同，保证流程状态可追踪、可恢复、可扩展。
"""

from datetime import datetime, timezone
from typing import Optional

from ludens_flow.core.paths import get_logs_dir, resolve_project_id


# 统一 UTC 时间格式，便于跨端检索与排序。
def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


# 节点级 trace 日志：记录 enter/leave 生命周期。
def write_trace_log(
    action: str,
    node: str,
    phase: str,
    frozen: bool,
    event_or_commit: str,
    error: str = "",
    project_id: Optional[str] = None,
) -> None:
    """
    trace.log: 每个节点进入/退出
    entering: ts | node | phase | frozen | last_event
    leaving: ts | node | commit=Y/N | error=...
    """
    logs_dir = get_logs_dir(resolve_project_id(project_id))
    logs_dir.mkdir(parents=True, exist_ok=True)
    trace_file = logs_dir / "trace.log"
    ts = _now_iso()
    with open(trace_file, "a", encoding="utf-8") as handle:
        if action.upper() == "ENTER":
            handle.write(
                f"[{ts}] ENTER | {node} | phase={phase} | frozen={frozen} | last_event={event_or_commit}\n"
            )
        elif action.upper() == "LEAVE":
            handle.write(
                f"[{ts}] LEAVE | {node} | commit={event_or_commit} | error={error}\n"
            )


# 路由决策日志：记录 phase 跳转与决策原因。
def write_router_log(
    iteration: int,
    from_phase: str,
    to_phase: str,
    choice: str,
    gate: str,
    frozen: bool,
    reason: str,
    project_id: Optional[str] = None,
) -> None:
    """
    router.log: 每次 Router 决策
    ts | iter | from_phase -> to_phase | choice | gate | frozen | reason
    """
    logs_dir = get_logs_dir(resolve_project_id(project_id))
    logs_dir.mkdir(parents=True, exist_ok=True)
    router_file = logs_dir / "router.log"
    ts = _now_iso()
    with open(router_file, "a", encoding="utf-8") as handle:
        handle.write(
            f"[{ts}] | iter={iteration} | {from_phase} -> {to_phase} | choice={choice} | gate={gate} | frozen={frozen} | reason={reason}\n"
        )


def write_audit_log(
    event: str,
    detail: str,
    actor: str = "system",
    project_id: Optional[str] = None,
) -> None:
    """Audit log for lifecycle operations like reset/migrate/export/import."""
    logs_dir = get_logs_dir(resolve_project_id(project_id))
    logs_dir.mkdir(parents=True, exist_ok=True)
    audit_file = logs_dir / "audit.log"
    ts = _now_iso()
    safe_detail = str(detail or "").replace("\n", " ").strip()
    with open(audit_file, "a", encoding="utf-8") as handle:
        handle.write(f"[{ts}] event={event} actor={actor} detail={safe_detail}\n")
