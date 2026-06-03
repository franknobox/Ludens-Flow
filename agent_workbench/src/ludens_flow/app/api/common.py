"""
文件功能：Web/API 入口层，向前端工作台提供状态、会话和项目操作接口。
核心内容：封装项目生命周期、workspace、settings、SSE 事件推送等 HTTP 能力。
核心内容：协调 graph/state/path 等 core 能力并返回前端可消费的数据结构。
关联文件：core/graph.py, core/paths.py, core/state/, capabilities/*
"""

import argparse
import asyncio
import base64
import json
import logging
import queue
import re
import uuid
import threading
from datetime import datetime, timezone
from pathlib import Path

import ludens_flow.core.state as st
from fastapi import HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from llm.model_profiles import list_model_profile_summaries
from ludens_flow.capabilities.ingest.attachment_ingest import (
    build_attachment_user_input,
    extract_attachment_text,
)
from ludens_flow.capabilities.artifacts.artifacts import read_artifact, write_artifact
from ludens_flow.capabilities.copywriting.design_copywriting import generate_design_copywriting
from ludens_flow.capabilities.context.user_profile import (
    format_profile_for_prompt,
    read_profile_file,
    write_profile_file,
)
from ludens_flow.capabilities.context.prompt_templates import load_prompt_template
from ludens_flow.capabilities.github import fetch_github_snapshot, parse_github_repo_ref
from ludens_flow.app.env import load_env_if_available
from ludens_flow.capabilities.mcp.health import check_mcp_connections
from ludens_flow.capabilities.paths import (
    get_project_github_repo,
    get_project_mcp_connections,
    set_project_github_repo,
    set_project_mcp_connections,
)
from ludens_flow.capabilities.skills.registry import (
    create_skill_draft,
    delete_skill,
    get_project_skills,
    import_external_skill_bundle,
    import_external_skill_github,
    import_external_skill,
    import_external_skill_zip,
    list_skills,
    set_project_skill_enabled,
)
from ludens_flow.capabilities.tools.registry import list_common_tools
from ludens_flow.core.graph import graph_step
from ludens_flow.core.router import Phase, phase_to_agent_key
from ludens_flow.core.agents.engineering_agent import EngineeringAgent
from ludens_flow.core.agents.pm_agent import PMAgent
from ludens_flow.core.agents.review_agent import ReviewAgent
from ludens_flow.core.paths import (
    add_project_workspace,
    archive_project,
    clear_project_unity_root,
    create_project,
    delete_project,
    get_dev_notes_assets_dir,
    get_project_settings,
    get_project_unity_root,
    list_project_workspaces,
    list_active_projects,
    list_archived_projects,
    list_projects,
    remove_project_workspace,
    rename_project,
    resolve_project_id,
    restore_project,
    set_project_agent_file_write_enabled,
    set_project_agent_file_write_confirm_required,
    set_project_engine_settings,
    set_project_model_routing,
    set_project_skill_self_capture_enabled,
    set_active_project_id,
    set_project_unity_root,
)
from ludens_flow.core.router import action_user_input, get_available_actions
from ludens_flow.core.schemas import normalize_design_copywriting_request
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

load_env_if_available()


_PROJECT_LOCKS: dict[str, threading.Lock] = {}
_PROJECT_LOCKS_GUARD = threading.Lock()
_EVENT_SUBSCRIBERS: dict[str, list[queue.Queue[dict]]] = {}
_EVENT_SUBSCRIBERS_GUARD = threading.Lock()
_PERMISSION_REQUESTS: dict[str, dict] = {}
_PERMISSION_REQUESTS_GUARD = threading.Lock()
_PERMISSION_REQUEST_TIMEOUT_SECONDS = 600
_COPYWRITING_JOBS: dict[str, dict] = {}
_COPYWRITING_JOBS_GUARD = threading.Lock()
_MAX_COPYWRITING_JOBS = 50

WORKBENCH_ROOT = Path(__file__).resolve().parents[4]
WEB_DIST_DIR = WORKBENCH_ROOT / "web" / "dist"
STATIC_DIR = WEB_DIST_DIR

def _project_relative_profile_path(project_id: str) -> str:
    return f"workspace/projects/{project_id}/USER_PROFILE.md"



class ChatRequest(BaseModel):
    message: str
    attachments: list[dict] | None = None
    mcp_mode: bool = False


class GddFastDevImportRequest(BaseModel):
    attachments: list[dict]
    project_info: dict[str, str] | None = None


class ProjectRequest(BaseModel):
    project_id: str | None = None
    display_name: str | None = None
    title: str | None = None


class UnityBindRequest(BaseModel):
    unity_root: str


class ProjectWorkspaceRequest(BaseModel):
    root: str
    kind: str = "unity"
    workspace_id: str | None = None
    label: str | None = None
    writable: bool = False
    enabled: bool = True


class ProjectSettingsRequest(BaseModel):
    agent_file_write_enabled: bool | None = None
    agent_file_write_confirm_required: bool | None = None
    skill_self_capture_enabled: bool | None = None
    model_routing: dict | None = None
    mcp_connections: list[dict] | None = None
    target_engine: str | None = None
    engine_profile: str | None = None
    allow_clear_mcp_connections: bool = False


class GithubRepoBindRequest(BaseModel):
    repo: str


class McpConnectionCheckRequest(BaseModel):
    connection_id: str | None = None
    engine: str | None = None


class PermissionDecisionRequest(BaseModel):
    approved: bool


class SkillImportRequest(BaseModel):
    manifest: dict | None = None
    prompt: str | None = None
    files: list[dict] | None = None
    zip_data_url: str | None = None
    github_url: str | None = None


class SkillDraftRequest(BaseModel):
    manifest: dict
    prompt: str
    source_agent: str | None = None
    reason: str | None = None


class ProjectSkillToggleRequest(BaseModel):
    enabled: bool


class UserProfileUpdateRequest(BaseModel):
    content: str = ""


class ActionRequest(BaseModel):
    action: str


class WorkspaceFileUpdateRequest(BaseModel):
    content: str = ""


class WorkspaceFileAssetUploadRequest(BaseModel):
    name: str = "pasted-image.png"
    data_url: str


class DesignCopywritingGenerateRequest(BaseModel):
    copy_type: str = "dialogue"
    brief: str = ""
    purpose: str = ""
    quantity: int = 5
    style: str = "简洁直给"
    length: str = "标准"
    must_include: list[str] | None = None
    must_avoid: list[str] | None = None
    reference_ids: list[str] | None = None
    external_references: list[dict] | None = None
    language: str = "zh-CN"


class DesignCopywritingJobCreateResponse(BaseModel):
    job_id: str
    status: str = "queued"


class ProjectExportRequest(BaseModel):
    output_path: str


class ProjectImportRequest(BaseModel):
    bundle_path: str
    project_id: str | None = None
    set_active: bool = True
    overwrite: bool = False


class ProjectRestoreRequest(BaseModel):
    set_active: bool = False


class ProjectRenameRequest(BaseModel):
    display_name: str


def _hide_obsolete_transition_message(item: dict) -> bool:
    if not isinstance(item, dict):
        return False
    if str(item.get("role") or "").lower() != "assistant":
        return False
    content = str(item.get("content") or "")
    return "发送任意消息即可继续" in content or "Send any message to continue" in content


def _visible_history(history) -> list:
    if not isinstance(history, list):
        return []
    return [
        item
        for item in history
        if not _hide_obsolete_transition_message(item)
    ]


def _state_to_json(state) -> dict:
    actions = get_available_actions(state)
    return {
        "project_id": getattr(state, "project_id", None),
        "schema_version": getattr(state, "schema_version", None),
        "phase": state.phase,
        "current_agent": phase_to_agent_key(state.phase),
        "iteration_count": state.iteration_count,
        "artifact_frozen": getattr(state, "artifact_frozen", False),
        "chat_history": _visible_history(getattr(state, "chat_history", [])),
        "transcript_history": _visible_history(getattr(state, "transcript_history", [])),
        "last_assistant_message": getattr(state, "last_assistant_message", None),
        "last_error": getattr(state, "last_error"),
        "review_gate": getattr(state, "review_gate"),
        "actions": actions,
        "needs_decision": bool(actions),
    }


def _get_project_lock(project_id: str) -> threading.Lock:
    with _PROJECT_LOCKS_GUARD:
        lock = _PROJECT_LOCKS.get(project_id)
        if lock is None:
            lock = threading.Lock()
            _PROJECT_LOCKS[project_id] = lock
        return lock


def _projects_payload() -> dict:
    return {
        "active_project": resolve_project_id(),
        "projects": list_projects(),
        "active_projects": list_active_projects(),
        "archived_projects": list_archived_projects(),
    }


def _subscribe_project_events(project_id: str) -> queue.Queue[dict]:
    subscriber: queue.Queue[dict] = queue.Queue()
    with _EVENT_SUBSCRIBERS_GUARD:
        _EVENT_SUBSCRIBERS.setdefault(project_id, []).append(subscriber)
    return subscriber


def _unsubscribe_project_events(project_id: str, subscriber: queue.Queue[dict]) -> None:
    with _EVENT_SUBSCRIBERS_GUARD:
        subscribers = _EVENT_SUBSCRIBERS.get(project_id)
        if not subscribers:
            return
        _EVENT_SUBSCRIBERS[project_id] = [
            existing for existing in subscribers if existing is not subscriber
        ]
        if not _EVENT_SUBSCRIBERS[project_id]:
            _EVENT_SUBSCRIBERS.pop(project_id, None)


def _publish_project_event(project_id: str, payload: dict) -> None:
    with _EVENT_SUBSCRIBERS_GUARD:
        subscribers = list(_EVENT_SUBSCRIBERS.get(project_id, []))
    for subscriber in subscribers:
        subscriber.put(payload)


def _publish_all_projects_event(payload: dict) -> None:
    with _EVENT_SUBSCRIBERS_GUARD:
        subscribers = {
            id(subscriber): subscriber
            for items in _EVENT_SUBSCRIBERS.values()
            for subscriber in items
        }.values()
    for subscriber in subscribers:
        subscriber.put(payload)


def _event_payload(
    event_type: str,
    *,
    project_id: str | None = None,
    state=None,
    error: str | None = None,
    message: str | None = None,
    include_projects: bool = False,
) -> dict:
    payload = {
        "type": event_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if project_id is not None:
        payload["project_id"] = project_id
    if state is not None:
        payload["state"] = _state_to_json(state)
        payload["phase"] = getattr(state, "phase", "")
        payload["current_agent"] = phase_to_agent_key(getattr(state, "phase", ""))
    if error:
        payload["error"] = error
    if message:
        payload["message"] = message
    if include_projects:
        payload.update(_projects_payload())
    return payload


def _format_sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _set_copywriting_job(job_id: str, update: dict) -> dict:
    with _COPYWRITING_JOBS_GUARD:
        existing = dict(_COPYWRITING_JOBS.get(job_id, {}))
        existing.update(update)
        existing["updated_at"] = datetime.now(timezone.utc).isoformat()
        _COPYWRITING_JOBS[job_id] = existing
        if len(_COPYWRITING_JOBS) > _MAX_COPYWRITING_JOBS:
            stale_ids = sorted(
                _COPYWRITING_JOBS,
                key=lambda item: str(_COPYWRITING_JOBS[item].get("updated_at", "")),
            )
            for stale_id in stale_ids[: len(_COPYWRITING_JOBS) - _MAX_COPYWRITING_JOBS]:
                _COPYWRITING_JOBS.pop(stale_id, None)
        return dict(existing)


def _get_copywriting_job(job_id: str) -> dict | None:
    with _COPYWRITING_JOBS_GUARD:
        job = _COPYWRITING_JOBS.get(job_id)
        return dict(job) if job else None


def _publish_copywriting_job_event(
    project_id: str,
    job_id: str,
    event_type: str,
    *,
    status: str,
    message: str | None = None,
    response: dict | None = None,
    error: str | None = None,
) -> None:
    payload = _event_payload(
        event_type,
        project_id=project_id,
        message=message,
        error=error,
    ) | {
        "job_id": job_id,
        "status": status,
    }
    if response is not None:
        payload["response"] = response
    _publish_project_event(project_id, payload)


def _build_stream_handler(project_id: str, state) -> callable:
    started = False

    def emit(delta: str) -> None:
        nonlocal started
        if not delta:
            return
        if not started:
            started = True
            _publish_project_event(
                project_id,
                _event_payload(
                    "assistant_stream_started",
                    project_id=project_id,
                    state=state,
                ),
            )
        _publish_project_event(
            project_id,
            _event_payload(
                "assistant_delta",
                project_id=project_id,
                state=state,
                message=None,
            )
            | {"delta": delta},
        )

    emit.has_started = lambda: started  # type: ignore[attr-defined]
    return emit


def _summarize_tool_call(tool_name: str, args: dict) -> str:
    if tool_name == "workspace_read_files_batch":
        paths = args.get("paths", []) if isinstance(args, dict) else []
        count = len(paths) if isinstance(paths, list) else 0
        workspace_id = (
            str(args.get("workspace_id", "") or "").strip()
            if isinstance(args, dict)
            else ""
        )
        workspace_note = f" @{workspace_id}" if workspace_id else ""
        return f"批量读取文件{workspace_note}：{count} 个"
    if tool_name == "workspace_create_directory":
        target_path = str(args.get("path", "") or "").strip() or "(未提供路径)"
        return f"创建目录：{target_path}"
    if tool_name == "workspace_write_text_file":
        target_path = str(args.get("path", "") or "").strip() or "(未提供路径)"
        return f"写入文件：{target_path}"
    if tool_name == "workspace_patch_text_file":
        target_path = str(args.get("path", "") or "").strip() or "(未提供路径)"
        return f"修改文件：{target_path}"
    if tool_name == "workspace_delete_file":
        target_path = str(args.get("path", "") or "").strip() or "(未提供路径)"
        return f"删除文件：{target_path}"
    if tool_name == "skill_create_draft":
        manifest = args.get("manifest", {}) if isinstance(args, dict) else {}
        name = str(manifest.get("name", "") or "").strip() if isinstance(manifest, dict) else ""
        return f"创建 Skill 草稿：{name or '(未命名)'}"
    if tool_name == "unity_list_dir":
        relative_path = str(args.get("relative_path", "") or "").strip() or "/"
        return f"列出目录：{relative_path}"
    if tool_name == "unity_read_file":
        relative_path = str(args.get("relative_path", "") or "").strip() or "(未提供路径)"
        return f"读取文件：{relative_path}"
    if tool_name == "unity_find_files":
        pattern = str(args.get("pattern", "*.cs") or "*.cs").strip()
        relative_path = str(args.get("relative_path", "") or "").strip() or "/"
        return f"查找文件：{relative_path} 内匹配 {pattern}"
    if tool_name.startswith("engine_"):
        engine = str(args.get("engine", "") or "").strip() or "engine"
        label = tool_name.replace("engine_", "engine.")
        return f"{engine} MCP: {label}"
    if tool_name == "web_search":
        query = str(args.get("query", "") or "").strip() or "(未提供关键词)"
        return f"搜索网络：{query}"
    return tool_name


def _summarize_tool_result(tool_name: str, result: str) -> str:
    text = str(result or "").strip()
    if not text:
        return "工具执行完成。"
    if tool_name in {
        "unity_list_dir",
        "unity_find_files",
        "workspace_read_files_batch",
        "skill_create_draft",
        "engine_list_scene",
        "engine_read_console",
    }:
        lines = [line for line in text.splitlines() if line.strip()]
        return f"共返回 {len(lines)} 行结果"
    return (text[:120] + "…") if len(text) > 120 else text


def _request_tool_permission(
    project_id: str, payload: dict, *, force_confirm: bool = False
) -> bool:
    if (
        not force_confirm
        and not get_project_settings(project_id=project_id).get(
            "agent_file_write_confirm_required", False
        )
    ):
        _publish_project_event(project_id, payload)
        return True

    request_id = uuid.uuid4().hex
    decision_event = threading.Event()
    record = {"event": decision_event, "approved": None}
    payload = payload | {"permission_request_id": request_id}

    with _PERMISSION_REQUESTS_GUARD:
        _PERMISSION_REQUESTS[request_id] = record

    _publish_project_event(project_id, payload)
    decision_event.wait(timeout=_PERMISSION_REQUEST_TIMEOUT_SECONDS)

    with _PERMISSION_REQUESTS_GUARD:
        _PERMISSION_REQUESTS.pop(request_id, None)

    return bool(record.get("approved"))


def _build_tool_event_handler(project_id: str, state) -> callable:
    def emit(event: dict):
        event_type = str(event.get("type", "") or "").strip()
        if not event_type:
            return
        tool_name = str(event.get("tool_name", "") or "").strip()
        args = event.get("args", {})
        payload = _event_payload(
            event_type,
            project_id=project_id,
            state=state,
        ) | {
            "tool_name": tool_name,
            "tool_summary": _summarize_tool_call(
                tool_name,
                args if isinstance(args, dict) else {},
            ),
        }
        if isinstance(args, dict):
            payload["workspace_id"] = str(args.get("workspace_id", "") or "")
            payload["file_path"] = str(
                args.get("path", "") or args.get("relative_path", "") or ""
            )
        if event_type in {
            "permission_required",
            "permission_granted",
            "permission_denied",
        }:
            payload["message"] = str(event.get("message", "") or "")
        if event_type == "tool_completed":
            payload["tool_result_summary"] = _summarize_tool_result(
                tool_name,
                str(event.get("result", "") or ""),
            )
        if event_type == "tool_progress":
            payload["message"] = str(event.get("message", "") or "")
        if event_type == "file_changed":
            payload["file_path"] = str(event.get("path", "") or "")
            payload["change_type"] = str(event.get("change_type", "") or "")
            payload["message"] = str(event.get("summary", "") or "")
        if event_type == "tool_failed":
            payload["error"] = str(event.get("error", "") or "工具执行失败。")
        if event_type == "permission_required":
            return _request_tool_permission(project_id, payload)
        _publish_project_event(project_id, payload)
        return None

    return emit


_SELF_SKILL_KEYWORDS = {
    "流程",
    "步骤",
    "规范",
    "工作流",
    "以后",
    "每次",
    "固定",
    "复用",
    "先",
    "然后",
    "最后",
    "必须",
    "不要",
    "输出",
    "检查",
}


def _looks_like_self_skill_candidate(message: str) -> bool:
    text = str(message or "").strip()
    if not text or text.startswith("/") or text.startswith("[ACTION]"):
        return False
    normalized = re.sub(r"\s+", "", text)
    lines = [line for line in text.splitlines() if line.strip()]
    numbered_steps = len(re.findall(r"(^|\n)\s*(?:\d+[.、)]|[-*])\s+", text))
    keyword_hits = sum(1 for keyword in _SELF_SKILL_KEYWORDS if keyword in text)
    return (
        len(normalized) >= 180
        or len(lines) >= 6
        or numbered_steps >= 3
        or (len(normalized) >= 110 and keyword_hits >= 4)
    )


def _self_skill_title_from_message(message: str) -> str:
    for line in str(message or "").splitlines():
        cleaned = re.sub(r"^[#>*\-\d.、)\s]+", "", line).strip()
        if cleaned:
            return cleaned[:28]
    return "项目工作流程"


def _build_self_skill_payload(message: str, state) -> tuple[dict, str, str]:
    agent_key = phase_to_agent_key(getattr(state, "phase", None))
    if agent_key not in {"design", "pm", "engineering", "review"}:
        agent_key = "engineering"
    title = _self_skill_title_from_message(message)
    suffix = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    manifest = {
        "id": f"self-{agent_key}-{suffix}-{uuid.uuid4().hex[:6]}",
        "name": title,
        "description": "从项目对话中沉淀的可复用工作流程。",
        "version": "0.1.0",
        "agents": [agent_key],
        "tags": ["自我沉淀", "流程"],
    }
    prompt = (
        f"# {title}\n\n"
        "## 使用场景\n"
        "当用户提出相似任务、希望复用稳定流程，或当前任务与下方流程高度相关时使用。\n\n"
        "## 原始流程\n"
        f"{message.strip()}\n\n"
        "## 执行规则\n"
        "- 优先把上述流程作为工作方法，而不是机械复述给用户。\n"
        "- 若流程与项目工件、当前用户最新指令冲突，以项目工件和最新指令为准。\n"
        "- 输出时保持当前 Agent 的职责边界，不越权进入其他阶段。\n"
        "- 发现流程不适用时，简要说明原因并按普通任务处理。\n"
    )
    return manifest, prompt, agent_key


def _maybe_create_self_skill_from_message(project_id: str, state, message: str) -> None:
    settings = get_project_settings(project_id=project_id)
    if not settings.get("skill_self_capture_enabled", False):
        return
    if not _looks_like_self_skill_candidate(message):
        return

    manifest, prompt, agent_key = _build_self_skill_payload(message, state)
    tool_name = "skill_create_draft"
    permission_payload = _event_payload(
        "permission_required",
        project_id=project_id,
        state=state,
    ) | {
        "tool_name": tool_name,
        "tool_summary": f"创建自我沉淀 Skill：{manifest['name']}",
        "message": "检测到这是一段可复用的任务流程。是否允许将它沉淀为当前项目可用的 Skill？",
        "workspace_id": "",
        "file_path": "workspace/skills/installed",
    }
    approved = _request_tool_permission(
        project_id,
        permission_payload,
        force_confirm=True,
    )
    if not approved:
        _publish_project_event(
            project_id,
            _event_payload(
                "permission_denied",
                project_id=project_id,
                state=state,
            )
            | {
                "tool_name": tool_name,
                "tool_summary": permission_payload["tool_summary"],
                "message": "用户取消了自我沉淀 Skill 创建。",
            },
        )
        return

    _publish_project_event(
        project_id,
        _event_payload("permission_granted", project_id=project_id, state=state)
        | {
            "tool_name": tool_name,
            "tool_summary": permission_payload["tool_summary"],
            "message": "已确认创建自我沉淀 Skill。",
        },
    )
    _publish_project_event(
        project_id,
        _event_payload("tool_started", project_id=project_id, state=state)
        | {
            "tool_name": tool_name,
            "tool_summary": permission_payload["tool_summary"],
        },
    )
    created = create_skill_draft(
        manifest,
        prompt=prompt,
        project_id=project_id,
        source_agent=agent_key,
        reason="auto_detected_long_workflow_prompt",
    )
    _publish_project_event(
        project_id,
        _event_payload("tool_completed", project_id=project_id, state=state)
        | {
            "tool_name": tool_name,
            "tool_summary": permission_payload["tool_summary"],
            "tool_result_summary": f"已创建自我沉淀 Skill：{created['name']}",
            "skill_id": created["id"],
        },
    )
    _publish_project_event(
        project_id,
        _event_payload("skills_updated", project_id=project_id, state=state)
        | {"skill_id": created["id"]},
    )


def startup() -> None:
    st.init_workspace()


def get_state(*args, **kwargs):
    from . import chat
    return chat.get_state(*args, **kwargs)


async def stream_project_events(*args, **kwargs):
    from . import events
    return await events.stream_project_events(*args, **kwargs)


def _build_user_input_payload(
    message: str,
    attachments: list[dict] | None = None,
):
    """Build multimodal/text chat payload from attachments."""
    return build_attachment_user_input(
        message,
        attachments=attachments,
        fallback_parser=None,
    )


def post_chat(*args, **kwargs):
    from . import chat
    return chat.post_chat(*args, **kwargs)


def post_action(*args, **kwargs):
    from . import chat
    return chat.post_action(*args, **kwargs)


def post_reset_current_project(*args, **kwargs):
    from . import projects
    return projects.post_reset_current_project(*args, **kwargs)


def get_current_project_unity_binding(*args, **kwargs):
    from . import workspaces
    return workspaces.get_current_project_unity_binding(*args, **kwargs)


def post_current_project_unity_bind(*args, **kwargs):
    from . import workspaces
    return workspaces.post_current_project_unity_bind(*args, **kwargs)


def post_current_project_unity_unbind(*args, **kwargs):
    from . import workspaces
    return workspaces.post_current_project_unity_unbind(*args, **kwargs)


def get_current_project_workspaces(*args, **kwargs):
    from . import workspaces
    return workspaces.get_current_project_workspaces(*args, **kwargs)


def get_current_project_settings(*args, **kwargs):
    from . import settings
    return settings.get_current_project_settings(*args, **kwargs)


def get_current_project_github(*args, **kwargs):
    from . import settings
    return settings.get_current_project_github(*args, **kwargs)


def post_current_project_github_bind(*args, **kwargs):
    from . import settings
    return settings.post_current_project_github_bind(*args, **kwargs)


def delete_current_project_github_bind(*args, **kwargs):
    from . import settings
    return settings.delete_current_project_github_bind(*args, **kwargs)


def get_model_profiles(*args, **kwargs):
    from . import settings
    return settings.get_model_profiles(*args, **kwargs)


def get_current_user_profile(*args, **kwargs):
    from . import settings
    return settings.get_current_user_profile(*args, **kwargs)


def post_current_user_profile(*args, **kwargs):
    from . import settings
    return settings.post_current_user_profile(*args, **kwargs)


def post_current_project_settings(*args, **kwargs):
    from . import settings
    return settings.post_current_project_settings(*args, **kwargs)


def delete_current_project_mcp_connection(*args, **kwargs):
    from . import settings
    return settings.delete_current_project_mcp_connection(*args, **kwargs)


def post_check_current_project_mcp_connections(*args, **kwargs):
    from . import settings
    return settings.post_check_current_project_mcp_connections(*args, **kwargs)


def post_permission_decision(*args, **kwargs):
    from . import settings
    return settings.post_permission_decision(*args, **kwargs)


def get_tool_catalog(*args, **kwargs):
    from . import settings
    return settings.get_tool_catalog(*args, **kwargs)


def get_skill_catalog(*args, **kwargs):
    from . import settings
    return settings.get_skill_catalog(*args, **kwargs)


def post_import_skill(*args, **kwargs):
    from . import settings
    return settings.post_import_skill(*args, **kwargs)


def post_skill_draft(*args, **kwargs):
    from . import settings
    return settings.post_skill_draft(*args, **kwargs)


def delete_installed_skill(*args, **kwargs):
    from . import settings
    return settings.delete_installed_skill(*args, **kwargs)


def get_current_project_skills(*args, **kwargs):
    from . import settings
    return settings.get_current_project_skills(*args, **kwargs)


def post_current_project_skill_toggle(*args, **kwargs):
    from . import settings
    return settings.post_current_project_skill_toggle(*args, **kwargs)


def post_current_project_workspace(*args, **kwargs):
    from . import workspaces
    return workspaces.post_current_project_workspace(*args, **kwargs)


def delete_current_project_workspace(*args, **kwargs):
    from . import workspaces
    return workspaces.delete_current_project_workspace(*args, **kwargs)


def post_reset(*args, **kwargs):
    from . import chat
    return chat.post_reset(*args, **kwargs)


def get_projects(*args, **kwargs):
    from . import projects
    return projects.get_projects(*args, **kwargs)


def post_project(*args, **kwargs):
    from . import projects
    return projects.post_project(*args, **kwargs)


def select_project(*args, **kwargs):
    from . import projects
    return projects.select_project(*args, **kwargs)


def post_archive_project(*args, **kwargs):
    from . import projects
    return projects.post_archive_project(*args, **kwargs)


def post_rename_project(*args, **kwargs):
    from . import projects
    return projects.post_rename_project(*args, **kwargs)


def post_restore_project(*args, **kwargs):
    from . import projects
    return projects.post_restore_project(*args, **kwargs)


def delete_archived_project(*args, **kwargs):
    from . import projects
    return projects.delete_archived_project(*args, **kwargs)


def post_export_current_project(*args, **kwargs):
    from . import projects
    return projects.post_export_current_project(*args, **kwargs)


def post_import_project_bundle(*args, **kwargs):
    from . import projects
    return projects.post_import_project_bundle(*args, **kwargs)


WORKSPACE_FILES = [
    {"id": "gdd", "name": "GDD.md", "artifact": "GDD", "owner": "DesignAgent"},
    {"id": "pm", "name": "PROJECT_PLAN.md", "artifact": "PROJECT_PLAN", "owner": "PMAgent"},
    {
        "id": "eng",
        "name": "IMPLEMENTATION_PLAN.md",
        "artifact": "IMPLEMENTATION_PLAN",
        "owner": "EngineeringAgent",
    },
    {
        "id": "review",
        "name": "REVIEW_REPORT.md",
        "artifact": "REVIEW_REPORT",
        "owner": "ReviewAgent",
    },
    {
        "id": "devlog",
        "name": "dev_notes/DEVLOG.md",
        "artifact": "DEVLOG",
        "owner": "EngineeringAgent",
    },
    {
        "id": "notes",
        "name": "dev_notes/NOTES.md",
        "artifact": "NOTES",
        "owner": "User",
    },
]


def list_workspace_files(*args, **kwargs):
    from . import workspaces
    return workspaces.list_workspace_files(*args, **kwargs)


def get_workspace_file_content(*args, **kwargs):
    from . import workspaces
    return workspaces.get_workspace_file_content(*args, **kwargs)


def put_workspace_file_content(*args, **kwargs):
    from . import workspaces
    return workspaces.put_workspace_file_content(*args, **kwargs)


def _imported_gdd_markdown(name: str, text: str, project_info: dict[str, str] | None) -> str:
    clean = str(text or "").strip()
    if not clean:
        raise ValueError("Imported GDD content is empty.")

    info_lines = []
    for key, value in (project_info or {}).items():
        value_text = str(value or "").strip()
        if value_text:
            info_lines.append(f"- {key}: {value_text}")

    if name.lower().endswith(".md"):
        body = clean
    else:
        body = f"# GDD\n\n> Source: {name}\n\n{clean}"

    if info_lines:
        return body.rstrip() + "\n\n## Project Info\n\n" + "\n".join(info_lines) + "\n"
    return body.rstrip() + "\n"


def _publish_fastdev_event(
    project_id: str,
    state,
    event_type: str,
    message: str,
    *,
    status: str,
    step: str | None = None,
) -> None:
    payload = _event_payload(
        event_type,
        project_id=project_id,
        state=state,
        message=message,
    ) | {"status": status}
    if step:
        payload["step"] = step
    _publish_project_event(project_id, payload)


def _commit_agent_artifact(project_id: str, state, result, actor: str) -> None:
    if result.state_updates:
        _merge_fastdev_state_updates(state, result.state_updates)
    if result.commit and result.commit.artifact_name and result.commit.content:
        write_artifact(
            result.commit.artifact_name,
            result.commit.content,
            reason=result.commit.reason or "Fast development auto generation",
            actor=actor,
            state=state,
            project_id=project_id,
            ignore_frozen=True,
        )
    for event in result.events or []:
        state.last_event = event


def _merge_fastdev_state_updates(state, updates: dict) -> None:
    """Merge artifact-generation state updates without importing graph internals."""
    if "drafts" in updates:
        for phase_key, items in updates["drafts"].items():
            if phase_key not in state.drafts:
                state.drafts[phase_key] = {}
            state.drafts[phase_key].update(items)

    if "change_requests" in updates:
        state.change_requests.extend(updates["change_requests"])

    if "decisions" in updates:
        state.decisions.extend(updates["decisions"])

    if "style_preset" in updates and updates["style_preset"]:
        state.style_preset = updates["style_preset"]

    if "review_gate" in updates:
        state.review_gate = updates["review_gate"]


def _apply_agent_prompt_template(agent, filename: str) -> None:
    template = load_prompt_template(filename)
    if not template:
        return
    system_prompt = template.build_system_prompt()
    if system_prompt:
        agent.system_prompt = system_prompt


def import_gdd_fastdev(*args, **kwargs):
    from . import workspaces
    return workspaces.import_gdd_fastdev(*args, **kwargs)


_NOTE_ASSET_MIME_EXTENSIONS = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "image/gif": ".gif",
}


def _safe_note_asset_name(raw_name: str, extension: str) -> str:
    stem = Path(str(raw_name or "pasted-image")).stem
    safe_stem = "".join(c if c.isalnum() or c in {"-", "_"} else "-" for c in stem)
    safe_stem = safe_stem.strip("-_") or "pasted-image"
    return f"{safe_stem}-{uuid.uuid4().hex[:8]}{extension}"


def upload_workspace_file_asset(*args, **kwargs):
    from . import workspaces
    return workspaces.upload_workspace_file_asset(*args, **kwargs)


def get_workspace_note_asset(*args, **kwargs):
    from . import workspaces
    return workspaces.get_workspace_note_asset(*args, **kwargs)


def post_generate_current_project_copywriting(*args, **kwargs):
    from . import copywriting
    return copywriting.post_generate_current_project_copywriting(*args, **kwargs)


def _run_copywriting_job(job_id: str, project_id: str, request_data: dict) -> None:
    def publish_progress(message: str) -> None:
        _set_copywriting_job(
            job_id,
            {
                "status": "running",
                "message": message,
            },
        )
        _publish_copywriting_job_event(
            project_id,
            job_id,
            "copywriting_job_progress",
            status="running",
            message=message,
        )

    try:
        publish_progress("正在整理加工要求与输出格式...")
        normalized_request = normalize_design_copywriting_request(request_data)
        response = generate_design_copywriting(
            normalized_request,
            project_id=project_id,
            external_references=request_data.get("external_references"),
            progress_handler=publish_progress,
        )
        response_payload = response.to_dict()
        _set_copywriting_job(
            job_id,
            {
                "status": "completed",
                "message": "生成完成。",
                "response": response_payload,
            },
        )
        _publish_copywriting_job_event(
            project_id,
            job_id,
            "copywriting_job_completed",
            status="completed",
            message="生成完成。",
            response=response_payload,
        )
    except Exception as exc:
        error_text = str(exc) or "Copywriting generation failed."
        logger.exception("copywriting job failed")
        _set_copywriting_job(
            job_id,
            {
                "status": "failed",
                "message": "生成失败。",
                "error": error_text,
            },
        )
        _publish_copywriting_job_event(
            project_id,
            job_id,
            "copywriting_job_failed",
            status="failed",
            message="生成失败。",
            error=error_text,
        )


def post_create_current_project_copywriting_job(*args, **kwargs):
    from . import copywriting
    return copywriting.post_create_current_project_copywriting_job(*args, **kwargs)


def get_current_project_copywriting_job(*args, **kwargs):
    from . import copywriting
    return copywriting.get_current_project_copywriting_job(*args, **kwargs)


def index():
    index_file = WEB_DIST_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {
        "message": "Ludens-Flow API. Build web frontend and mount static assets at /static."
    }
