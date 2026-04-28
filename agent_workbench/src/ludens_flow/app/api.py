"""
文件功能：Web/API 入口层，向前端工作台提供状态、会话和项目操作接口。
核心内容：封装项目生命周期、workspace、settings、SSE 事件推送等 HTTP 能力。
核心内容：协调 graph/state/path 等 core 能力并返回前端可消费的数据结构。
关联文件：core/graph.py, core/paths.py, core/state/, capabilities/*
"""

import argparse
import asyncio
import json
import logging
import queue
import uuid
import threading
from datetime import datetime, timezone
from pathlib import Path

import ludens_flow.core.state as st
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from ludens_flow.capabilities.ingest.attachment_ingest import build_attachment_user_input
from ludens_flow.capabilities.artifacts.artifacts import read_artifact, write_artifact
from ludens_flow.app.env import load_env_if_available
from ludens_flow.capabilities.tools.registry import list_common_tools
from ludens_flow.core.graph import graph_step
from ludens_flow.core.paths import (
    add_project_workspace,
    archive_project,
    clear_project_unity_root,
    create_project,
    delete_project,
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
    set_project_model_routing,
    set_active_project_id,
    set_project_unity_root,
)
from ludens_flow.core.router import action_user_input, get_available_actions
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

load_env_if_available()

app = FastAPI(title="Ludens-Flow API")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)

_PROJECT_LOCKS: dict[str, threading.Lock] = {}
_PROJECT_LOCKS_GUARD = threading.Lock()
_EVENT_SUBSCRIBERS: dict[str, list[queue.Queue[dict]]] = {}
_EVENT_SUBSCRIBERS_GUARD = threading.Lock()
_PERMISSION_REQUESTS: dict[str, dict] = {}
_PERMISSION_REQUESTS_GUARD = threading.Lock()

WORKBENCH_ROOT = Path(__file__).resolve().parents[3]
WEB_DIST_DIR = WORKBENCH_ROOT / "web" / "dist"
STATIC_DIR = WEB_DIST_DIR

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


class ChatRequest(BaseModel):
    message: str
    attachments: list[dict] | None = None


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
    model_routing: dict | None = None


class PermissionDecisionRequest(BaseModel):
    approved: bool


class ActionRequest(BaseModel):
    action: str


class WorkspaceFileUpdateRequest(BaseModel):
    content: str = ""


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


def _phase_to_agent_key(phase: str | None) -> str:
    if not phase:
        return "system"
    if phase.startswith("GDD_"):
        return "design"
    if phase.startswith("PM_"):
        return "pm"
    if phase.startswith("ENG_") or phase == "DEV_COACHING":
        return "engineering"
    if phase.startswith("REVIEW") or phase == "POST_REVIEW_DECISION":
        return "review"
    return "system"


def _state_to_json(state) -> dict:
    actions = get_available_actions(state)
    return {
        "project_id": getattr(state, "project_id", None),
        "schema_version": getattr(state, "schema_version", None),
        "phase": state.phase,
        "current_agent": _phase_to_agent_key(state.phase),
        "iteration_count": state.iteration_count,
        "artifact_frozen": getattr(state, "artifact_frozen", False),
        "chat_history": getattr(state, "chat_history", []),
        "transcript_history": getattr(state, "transcript_history", []),
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
        payload["current_agent"] = _phase_to_agent_key(getattr(state, "phase", ""))
    if error:
        payload["error"] = error
    if message:
        payload["message"] = message
    if include_projects:
        payload.update(_projects_payload())
    return payload


def _format_sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


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
    }:
        lines = [line for line in text.splitlines() if line.strip()]
        return f"共返回 {len(lines)} 行结果"
    return (text[:120] + "…") if len(text) > 120 else text


def _request_tool_permission(project_id: str, payload: dict) -> bool:
    if not get_project_settings(project_id=project_id).get(
        "agent_file_write_confirm_required", False
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
    decision_event.wait(timeout=90)

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


@app.on_event("startup")
def startup() -> None:
    st.init_workspace()


@app.get("/api/state")
def get_state():
    state = st.load_state()
    return _state_to_json(state)


@app.get("/api/projects/{project_id}/events")
async def stream_project_events(project_id: str):
    resolved_project_id = resolve_project_id(project_id)
    if not resolved_project_id:
        raise HTTPException(status_code=404, detail="Project not found")

    subscriber = _subscribe_project_events(resolved_project_id)

    async def event_stream():
        try:
            initial_state = st.load_state(project_id=resolved_project_id)
            yield _format_sse(
                _event_payload(
                    "connected",
                    project_id=resolved_project_id,
                    state=initial_state,
                    include_projects=True,
                )
            )

            while True:
                try:
                    payload = await asyncio.to_thread(subscriber.get, True, 15)
                except queue.Empty:
                    yield ": keep-alive\n\n"
                    continue
                yield _format_sse(payload)
        finally:
            _unsubscribe_project_events(resolved_project_id, subscriber)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


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


@app.post("/api/chat")
def post_chat(req: ChatRequest):
    project_id = resolve_project_id()
    lock = _get_project_lock(project_id)
    user_message = req.message.strip()

    with lock:
        state = st.load_state(project_id=project_id)

        if user_message.lower().startswith("/unity bind "):
            unity_root = user_message[len("/unity bind ") :].strip().strip('"')
            try:
                meta = set_project_unity_root(unity_root, project_id=project_id)
                return {
                    "reply": f"Unity project bound: {meta.get('unity_root', '')}",
                    "phase": state.phase,
                    "error": None,
                    "needs_decision": bool(get_available_actions(state)),
                    "review_gate": state.review_gate,
                    "actions": get_available_actions(state),
                }
            except Exception as e:
                return {
                    "reply": "",
                    "phase": state.phase,
                    "error": str(e),
                    "needs_decision": bool(get_available_actions(state)),
                    "review_gate": state.review_gate,
                    "actions": get_available_actions(state),
                }

        if user_message.lower() == "/unity unbind":
            meta = clear_project_unity_root(project_id=project_id)
            return {
                "reply": f"Unity project unbound for {meta['id']}.",
                "phase": state.phase,
                "error": None,
                "needs_decision": bool(get_available_actions(state)),
                "review_gate": state.review_gate,
                "actions": get_available_actions(state),
            }

        payload = _build_user_input_payload(user_message, req.attachments)
        user_input = payload.user_input
        if not (isinstance(user_input, str) and user_input) and not (
            isinstance(user_input, list) and user_input
        ):
            return {
                "reply": "",
                "phase": state.phase,
                "error": "输入不能为空",
                "attachment_warnings": payload.warnings,
                "needs_decision": bool(get_available_actions(state)),
                "actions": get_available_actions(state),
            }

        try:
            stream_handler = _build_stream_handler(project_id, state)
            tool_event_handler = _build_tool_event_handler(project_id, state)
            _publish_project_event(
                project_id,
                _event_payload(
                    "run_started",
                    project_id=project_id,
                    state=state,
                    message=user_message or "[multimodal input]",
                ),
            )
            state = graph_step(
                state,
                user_input,
                stream_handler=stream_handler,
                tool_event_handler=tool_event_handler,
            )
            reply = getattr(state, "last_assistant_message", "") or ""
            state.last_assistant_message = None
            st.save_state(state, project_id=project_id)
            actions = get_available_actions(state)
            if getattr(stream_handler, "has_started", lambda: False)():
                _publish_project_event(
                    project_id,
                    _event_payload(
                        "assistant_stream_completed",
                        project_id=project_id,
                        state=state,
                    ),
                )
            _publish_project_event(
                project_id,
                _event_payload(
                    "state_updated",
                    project_id=project_id,
                    state=state,
                    include_projects=True,
                ),
            )
            return {
                "reply": reply,
                "phase": state.phase,
                "error": getattr(state, "last_error"),
                "attachment_warnings": payload.warnings,
                "needs_decision": bool(actions),
                "review_gate": state.review_gate,
                "actions": actions,
            }
        except Exception as e:
            logger.exception("chat error")
            state.last_error = str(e)
            st.save_state(state, project_id=project_id)
            actions = get_available_actions(state)
            _publish_project_event(
                project_id,
                _event_payload(
                    "run_failed",
                    project_id=project_id,
                    state=state,
                    error=str(e),
                    include_projects=True,
                ),
            )
            return {
                "reply": "",
                "phase": state.phase,
                "error": str(e),
                "attachment_warnings": payload.warnings,
                "needs_decision": bool(actions),
                "actions": actions,
            }


@app.post("/api/actions")
def post_action(req: ActionRequest):
    project_id = resolve_project_id()
    lock = _get_project_lock(project_id)

    with lock:
        state = st.load_state(project_id=project_id)
        actions = get_available_actions(state)
        allowed_ids = {item["id"] for item in actions}
        action_id = req.action.strip().lower()

        if action_id not in allowed_ids:
            return {
                "reply": "",
                "phase": state.phase,
                "error": f"Invalid action '{req.action}' for current phase.",
                "needs_decision": bool(actions),
                "review_gate": state.review_gate,
                "actions": actions,
            }

        try:
            stream_handler = _build_stream_handler(project_id, state)
            tool_event_handler = _build_tool_event_handler(project_id, state)
            _publish_project_event(
                project_id,
                _event_payload(
                    "run_started",
                    project_id=project_id,
                    state=state,
                    message=f"[ACTION] {action_id}",
                ),
            )
            synthetic_input = action_user_input(action_id)
            state = graph_step(
                state,
                synthetic_input,
                explicit_action=action_id,
                stream_handler=stream_handler,
                tool_event_handler=tool_event_handler,
            )
            reply = getattr(state, "last_assistant_message", "") or ""
            state.last_assistant_message = None
            st.save_state(state, project_id=project_id)
            next_actions = get_available_actions(state)
            if getattr(stream_handler, "has_started", lambda: False)():
                _publish_project_event(
                    project_id,
                    _event_payload(
                        "assistant_stream_completed",
                        project_id=project_id,
                        state=state,
                    ),
                )
            _publish_project_event(
                project_id,
                _event_payload(
                    "state_updated",
                    project_id=project_id,
                    state=state,
                    include_projects=True,
                ),
            )
            return {
                "reply": reply,
                "phase": state.phase,
                "error": getattr(state, "last_error"),
                "needs_decision": bool(next_actions),
                "review_gate": state.review_gate,
                "actions": next_actions,
            }
        except Exception as e:
            logger.exception("action error")
            state.last_error = str(e)
            st.save_state(state, project_id=project_id)
            actions = get_available_actions(state)
            _publish_project_event(
                project_id,
                _event_payload(
                    "run_failed",
                    project_id=project_id,
                    state=state,
                    error=str(e),
                    include_projects=True,
                ),
            )
            return {
                "reply": "",
                "phase": state.phase,
                "error": str(e),
                "needs_decision": bool(actions),
                "review_gate": state.review_gate,
                "actions": actions,
            }


@app.post("/api/projects/current/reset")
def post_reset_current_project():
    state = st.load_state()
    state = st.reset_current_project_state(
        clear_images=True, project_id=getattr(state, "project_id", None)
    )
    _publish_project_event(
        getattr(state, "project_id", ""),
        _event_payload(
            "state_updated",
            project_id=getattr(state, "project_id", None),
            state=state,
            include_projects=True,
        ),
    )
    return _state_to_json(state)


@app.get("/api/projects/current/unity")
def get_current_project_unity_binding():
    project_id = resolve_project_id()
    unity_root = get_project_unity_root(project_id)
    exists = bool(unity_root and Path(unity_root).exists())
    workspaces = list_project_workspaces(project_id=project_id, kind="unity")
    return {
        "project_id": project_id,
        "unity_root": unity_root,
        "bound": bool(unity_root),
        "exists": exists,
        "workspaces": workspaces,
    }


@app.post("/api/projects/current/unity/bind")
def post_current_project_unity_bind(req: UnityBindRequest):
    project_id = resolve_project_id()
    meta = set_project_unity_root(req.unity_root, project_id=project_id)
    return {
        "project_id": project_id,
        "unity_root": meta.get("unity_root", ""),
        "bound": bool(meta.get("unity_root", "")),
        "workspaces": meta.get("workspaces", []),
    }


@app.post("/api/projects/current/unity/unbind")
def post_current_project_unity_unbind():
    project_id = resolve_project_id()
    meta = clear_project_unity_root(project_id=project_id)
    return {
        "project_id": project_id,
        "unity_root": meta.get("unity_root", ""),
        "bound": False,
        "workspaces": meta.get("workspaces", []),
    }


@app.get("/api/projects/current/workspaces")
def get_current_project_workspaces():
    project_id = resolve_project_id()
    return {
        "project_id": project_id,
        "workspaces": list_project_workspaces(project_id=project_id, include_disabled=True),
    }


@app.get("/api/projects/current/settings")
def get_current_project_settings():
    project_id = resolve_project_id()
    return get_project_settings(project_id=project_id)


@app.post("/api/projects/current/settings")
def post_current_project_settings(req: ProjectSettingsRequest):
    project_id = resolve_project_id()
    if (
        req.agent_file_write_enabled is None
        and req.agent_file_write_confirm_required is None
        and req.model_routing is None
    ):
        raise HTTPException(status_code=400, detail="No settings field provided.")

    if req.agent_file_write_enabled is not None:
        set_project_agent_file_write_enabled(
            req.agent_file_write_enabled,
            project_id=project_id,
        )

    if req.agent_file_write_confirm_required is not None:
        set_project_agent_file_write_confirm_required(
            req.agent_file_write_confirm_required,
            project_id=project_id,
        )

    if req.model_routing is not None:
        set_project_model_routing(
            req.model_routing,
            project_id=project_id,
        )

    return get_project_settings(project_id=project_id)


@app.post("/api/permissions/{request_id}/decision")
def post_permission_decision(request_id: str, req: PermissionDecisionRequest):
    with _PERMISSION_REQUESTS_GUARD:
        record = _PERMISSION_REQUESTS.get(request_id)
    if not record:
        raise HTTPException(status_code=404, detail="Permission request not found.")

    record["approved"] = bool(req.approved)
    record["event"].set()
    return {"permission_request_id": request_id, "approved": bool(req.approved)}


@app.get("/api/tools")
def get_tool_catalog():
    return {
        "tools": list_common_tools(),
    }


@app.post("/api/projects/current/workspaces")
def post_current_project_workspace(req: ProjectWorkspaceRequest):
    project_id = resolve_project_id()
    try:
        meta = add_project_workspace(
            req.root,
            project_id=project_id,
            kind=req.kind,
            workspace_id=req.workspace_id,
            label=req.label,
            writable=req.writable,
            enabled=req.enabled,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    workspaces = meta.get("workspaces", [])
    normalized_root = str(Path(req.root).expanduser().resolve())
    added_workspace = next(
        (
            item
            for item in workspaces
            if item.get("root") == normalized_root and item.get("kind") == req.kind.lower()
        ),
        None,
    )
    return {
        "project_id": project_id,
        "workspace": added_workspace,
        "workspaces": workspaces,
    }


@app.delete("/api/projects/current/workspaces/{workspace_id}")
def delete_current_project_workspace(workspace_id: str):
    project_id = resolve_project_id()
    try:
        meta = remove_project_workspace(workspace_id, project_id=project_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "project_id": project_id,
        "workspaces": meta.get("workspaces", []),
    }


@app.post("/api/reset")
def post_reset():
    return post_reset_current_project()


@app.get("/api/projects")
def get_projects():
    return {
        "active_project": resolve_project_id(),
        "projects": list_projects(),
        "active_projects": list_active_projects(),
        "archived_projects": list_archived_projects(),
    }


@app.post("/api/projects")
def post_project(req: ProjectRequest):
    meta = create_project(
        req.project_id,
        display_name=req.display_name,
        title=req.title,
        set_active=True,
    )
    st.init_workspace(project_id=meta["id"])
    state = st.load_state(project_id=meta["id"])
    _publish_all_projects_event(
        _event_payload("projects_updated", include_projects=True)
    )
    _publish_project_event(
        meta["id"],
        _event_payload(
            "state_updated",
            project_id=meta["id"],
            state=state,
            include_projects=True,
        ),
    )
    return {
        "project": meta,
        "state": _state_to_json(state),
    }


@app.post("/api/projects/{project_id}/select")
def select_project(project_id: str):
    active_project = set_active_project_id(project_id)
    st.init_workspace(project_id=active_project)
    state = st.load_state(project_id=active_project)
    _publish_all_projects_event(
        _event_payload("projects_updated", include_projects=True)
    )
    return {
        "active_project": active_project,
        "state": _state_to_json(state),
    }


@app.post("/api/projects/{project_id}/archive")
def post_archive_project(project_id: str):
    archived = archive_project(project_id)
    active_project = resolve_project_id()
    state = st.load_state(project_id=active_project)
    _publish_all_projects_event(
        _event_payload("projects_updated", include_projects=True)
    )
    _publish_project_event(
        active_project,
        _event_payload(
            "state_updated",
            project_id=active_project,
            state=state,
            include_projects=True,
        ),
    )
    return {
        "project": archived,
        "active_project": active_project,
        "state": _state_to_json(state),
        "projects": list_projects(),
        "active_projects": list_active_projects(),
        "archived_projects": list_archived_projects(),
    }


@app.post("/api/projects/{project_id}/rename")
def post_rename_project(project_id: str, req: ProjectRenameRequest):
    renamed = rename_project(project_id, req.display_name)
    active_project = resolve_project_id()
    state = st.load_state(project_id=active_project)
    _publish_all_projects_event(
        _event_payload("projects_updated", include_projects=True)
    )
    _publish_project_event(
        active_project,
        _event_payload(
            "state_updated",
            project_id=active_project,
            state=state,
            include_projects=True,
        ),
    )
    return {
        "project": renamed,
        "active_project": active_project,
        "state": _state_to_json(state),
        "projects": list_projects(),
        "active_projects": list_active_projects(),
        "archived_projects": list_archived_projects(),
    }


@app.post("/api/projects/{project_id}/restore")
def post_restore_project(project_id: str, req: ProjectRestoreRequest | None = None):
    restore_req = req or ProjectRestoreRequest()
    restored = restore_project(project_id, set_active=restore_req.set_active)
    active_project = resolve_project_id()
    state = st.load_state(project_id=active_project)
    _publish_all_projects_event(
        _event_payload("projects_updated", include_projects=True)
    )
    _publish_project_event(
        active_project,
        _event_payload(
            "state_updated",
            project_id=active_project,
            state=state,
            include_projects=True,
        ),
    )
    return {
        "project": restored,
        "active_project": active_project,
        "state": _state_to_json(state),
        "projects": list_projects(),
        "active_projects": list_active_projects(),
        "archived_projects": list_archived_projects(),
    }


@app.delete("/api/projects/{project_id}")
def delete_archived_project(project_id: str):
    deleted_project = delete_project(project_id)
    _publish_all_projects_event(
        _event_payload("projects_updated", include_projects=True)
    )
    return {
        "deleted_project": deleted_project,
        "active_project": resolve_project_id(),
        "projects": list_projects(),
        "active_projects": list_active_projects(),
        "archived_projects": list_archived_projects(),
    }


@app.post("/api/projects/current/export")
def post_export_current_project(req: ProjectExportRequest):
    state = st.load_state()
    project_id = getattr(state, "project_id", None)
    bundle = st.export_project_bundle(req.output_path, project_id=project_id)
    return {
        "project_id": project_id,
        "bundle_path": str(bundle),
    }


@app.post("/api/projects/import")
def post_import_project_bundle(req: ProjectImportRequest):
    imported_project = st.import_project_bundle(
        req.bundle_path,
        project_id=req.project_id,
        set_active=req.set_active,
        overwrite=req.overwrite,
    )
    state = st.load_state(project_id=imported_project)
    return {
        "project_id": imported_project,
        "state": _state_to_json(state),
    }


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
]


@app.get("/api/workspace/files")
def list_workspace_files():
    return {"files": WORKSPACE_FILES}


@app.get("/api/workspace/files/{file_id}/content")
def get_workspace_file_content(file_id: str):
    state = st.load_state()
    for f in WORKSPACE_FILES:
        if f["id"] == file_id:
            try:
                content = read_artifact(
                    f["artifact"], project_id=getattr(state, "project_id", None)
                )
                return {"id": file_id, "name": f["name"], "content": content}
            except Exception as e:
                logger.warning(f"Read artifact {file_id}: {e}")
                return {"id": file_id, "name": f["name"], "content": ""}
    raise HTTPException(status_code=404, detail="Not found")


@app.put("/api/workspace/files/{file_id}/content")
def put_workspace_file_content(file_id: str, req: WorkspaceFileUpdateRequest):
    state = st.load_state()
    project_id = resolve_project_id(getattr(state, "project_id", None))

    for f in WORKSPACE_FILES:
        if f["id"] != file_id:
            continue

        try:
            write_artifact(
                f["artifact"],
                req.content,
                reason="Manual edit from workbench",
                actor=f["owner"],
                state=state,
                project_id=project_id,
                ignore_frozen=True,
            )
            st.save_state(state, project_id=project_id)
            updated_content = read_artifact(f["artifact"], project_id=project_id)
        except PermissionError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        except RuntimeError as e:
            raise HTTPException(status_code=409, detail=str(e)) from e
        except Exception as e:
            logger.warning(f"Write artifact {file_id}: {e}")
            raise HTTPException(status_code=500, detail="保存工件失败") from e

        _publish_project_event(
            project_id,
            _event_payload(
                "state_updated",
                project_id=project_id,
                state=state,
                include_projects=True,
            ),
        )

        return {
            "id": file_id,
            "name": f["name"],
            "content": updated_content,
            "state": _state_to_json(state),
        }

    raise HTTPException(status_code=404, detail="Not found")


@app.get("/")
def index():
    index_file = WEB_DIST_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {
        "message": "Ludens-Flow API. Build web frontend and mount static assets at /static."
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Ludens-Flow API server runner")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host")
    parser.add_argument("--port", type=int, default=8011, help="Bind port")
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable uvicorn auto-reload",
    )
    args = parser.parse_args()

    import uvicorn

    uvicorn.run(
        "ludens_flow.app.api:app", host=args.host, port=args.port, reload=args.reload
    )


if __name__ == "__main__":
    main()
