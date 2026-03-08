"""
Ludens-Flow 前端 API：提供 state、chat、reset，供飞书风格 Web 前端调用。
运行方式（在项目根目录）：uvicorn agent_workbench.api:app --reload
"""
import logging
import sys
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
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

FRONTEND_DIR = Path(__file__).resolve().parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


class ChatRequest(BaseModel):
    message: str
    images: list[str] | None = None  # data URI 列表，如 data:image/png;base64,...


def _state_to_json(state) -> dict:
    return {
        "phase": state.phase,
        "iteration_count": state.iteration_count,
        "artifact_frozen": getattr(state, "artifact_frozen", False),
        "chat_history": getattr(state, "chat_history", []),
        "last_error": getattr(state, "last_error"),
        "review_gate": getattr(state, "review_gate"),
    }


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
    state = st.load_state()
    user_input = _build_user_input(req.message.strip(), req.images)
    if not (isinstance(user_input, str) and user_input) and not (isinstance(user_input, list) and user_input):
        return {"reply": "", "phase": state.phase, "error": "输入不能为空", "needs_decision": False}
    try:
        state = graph_step(state, user_input)
        st.save_state(state)
        reply = getattr(state, "last_assistant_message", "") or ""
        state.last_assistant_message = None
        st.save_state(state)
        needs = state.phase == "POST_REVIEW_DECISION"
        return {
            "reply": reply,
            "phase": state.phase,
            "error": getattr(state, "last_error"),
            "needs_decision": needs,
            "review_gate": state.review_gate,
        }
    except Exception as e:
        logger.exception("chat error")
        state.last_error = str(e)
        st.save_state(state)
        return {"reply": "", "phase": state.phase, "error": str(e), "needs_decision": False}


@app.post("/api/reset")
def post_reset():
    state = st.reset_workspace_state(clear_images=True)
    return _state_to_json(state)


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
    for f in WORKSPACE_FILES:
        if f["id"] == file_id:
            try:
                content = read_artifact(f["artifact"])
                return {"id": file_id, "name": f["name"], "content": content}
            except Exception as e:
                logger.warning(f"Read artifact {file_id}: {e}")
                return {"id": file_id, "name": f["name"], "content": ""}
    raise HTTPException(status_code=404, detail="Not found")


@app.get("/")
def index():
    index_file = FRONTEND_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"message": "Ludens-Flow API. Mount frontend at /static and add index at /"}
