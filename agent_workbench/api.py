"""
Ludens-Flow 前端 API：提供 state、chat、reset，供 Web 前端调用。
运行方式（在项目根目录）：uvicorn agent_workbench.api:app --reload
"""

import logging
import sys
import threading
from pathlib import Path

_here = Path(__file__).resolve().parent
sys.path.insert(0, str(_here))
sys.path.insert(0, str(_here / "src"))
try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

import ludens_flow.state as st
from ludens_flow.graph import graph_step
from ludens_flow.artifacts import read_artifact
from ludens_flow.router import action_user_input, get_available_actions
from ludens_flow.paths import (
    clear_project_unity_root,
    create_project,
    get_project_unity_root,
    list_projects,
    resolve_project_id,
    set_project_unity_root,
    set_active_project_id,
)

# 复用 run_agents 的输入解析（含图片路径）
from run_agents import parse_user_input

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

app = FastAPI(title="Ludens-Flow API")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)

_PROJECT_LOCKS: dict[str, threading.Lock] = {}
_PROJECT_LOCKS_GUARD = threading.Lock()

WEB_DIST_DIR = Path(__file__).resolve().parent / "web" / "dist"
STATIC_DIR = WEB_DIST_DIR

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


class ChatRequest(BaseModel):
    message: str
    images: list[str] | None = None  # data URI 列表，如 data:image/png;base64,...


class ProjectRequest(BaseModel):
    project_id: str
    display_name: str | None = None
    title: str | None = None


class UnityBindRequest(BaseModel):
    unity_root: str


class ActionRequest(BaseModel):
    action: str


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


@app.on_event("startup")
def startup():
    st.init_workspace()


@app.get("/api/state")
def get_state():
    state = st.load_state()
    return _state_to_json(state)


def _build_user_input(message: str, images: list[str] | None):
    """文本 + 前端上传的图片 → 多模态 payload 或纯文本。"""
    if images:
        payload = []
        if message.strip():
            payload.append({"type": "text", "text": message.strip()})
        for url in images:
            if url.startswith("data:"):
                payload.append({"type": "image_url", "image_url": {"url": url}})
        return payload if payload else (message.strip() or "")
    return parse_user_input(message)


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

        user_input = _build_user_input(user_message, req.images)
        if not (isinstance(user_input, str) and user_input) and not (
            isinstance(user_input, list) and user_input
        ):
            return {
                "reply": "",
                "phase": state.phase,
                "error": "输入不能为空",
                "needs_decision": bool(get_available_actions(state)),
                "actions": get_available_actions(state),
            }

        try:
            state = graph_step(state, user_input)
            reply = getattr(state, "last_assistant_message", "") or ""
            state.last_assistant_message = None
            st.save_state(state, project_id=project_id)
            actions = get_available_actions(state)
            return {
                "reply": reply,
                "phase": state.phase,
                "error": getattr(state, "last_error"),
                "needs_decision": bool(actions),
                "review_gate": state.review_gate,
                "actions": actions,
            }
        except Exception as e:
            logger.exception("chat error")
            state.last_error = str(e)
            st.save_state(state, project_id=project_id)
            actions = get_available_actions(state)
            return {
                "reply": "",
                "phase": state.phase,
                "error": str(e),
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
            synthetic_input = action_user_input(action_id)
            state = graph_step(state, synthetic_input, explicit_action=action_id)
            reply = getattr(state, "last_assistant_message", "") or ""
            state.last_assistant_message = None
            st.save_state(state, project_id=project_id)
            next_actions = get_available_actions(state)
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
    return _state_to_json(state)


@app.get("/api/projects/current/unity")
def get_current_project_unity_binding():
    project_id = resolve_project_id()
    unity_root = get_project_unity_root(project_id)
    exists = bool(unity_root and Path(unity_root).exists())
    return {
        "project_id": project_id,
        "unity_root": unity_root,
        "bound": bool(unity_root),
        "exists": exists,
    }


@app.post("/api/projects/current/unity/bind")
def post_current_project_unity_bind(req: UnityBindRequest):
    project_id = resolve_project_id()
    meta = set_project_unity_root(req.unity_root, project_id=project_id)
    return {
        "project_id": project_id,
        "unity_root": meta.get("unity_root", ""),
        "bound": bool(meta.get("unity_root", "")),
    }


@app.post("/api/projects/current/unity/unbind")
def post_current_project_unity_unbind():
    project_id = resolve_project_id()
    meta = clear_project_unity_root(project_id=project_id)
    return {
        "project_id": project_id,
        "unity_root": meta.get("unity_root", ""),
        "bound": False,
    }


@app.post("/api/reset")
def post_reset():
    return post_reset_current_project()


@app.get("/api/projects")
def get_projects():
    return {
        "active_project": resolve_project_id(),
        "projects": list_projects(),
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
    return {
        "project": meta,
        "state": _state_to_json(state),
    }


@app.post("/api/projects/{project_id}/select")
def select_project(project_id: str):
    active_project = set_active_project_id(project_id)
    st.init_workspace(project_id=active_project)
    state = st.load_state(project_id=active_project)
    return {
        "active_project": active_project,
        "state": _state_to_json(state),
    }


# 工作区文件（Agent 产出）列表与内容
WORKSPACE_FILES = [
    {"id": "gdd", "name": "GDD.md", "artifact": "GDD"},
    {"id": "pm", "name": "PROJECT_PLAN.md", "artifact": "PROJECT_PLAN"},
    {"id": "eng", "name": "IMPLEMENTATION_PLAN.md", "artifact": "IMPLEMENTATION_PLAN"},
    {"id": "review", "name": "REVIEW_REPORT.md", "artifact": "REVIEW_REPORT"},
    {"id": "devlog", "name": "dev_notes/DEVLOG.md", "artifact": "DEVLOG"},
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


@app.get("/")
def index():
    index_file = WEB_DIST_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {
        "message": "Ludens-Flow API. Build web frontend and mount static assets at /static."
    }
