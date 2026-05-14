import argparse
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import chat, common, copywriting, events, projects, settings, workspaces
from .common import *  # Re-export legacy direct-call API used by tests and scripts.

_subscribe_project_events = common._subscribe_project_events
_unsubscribe_project_events = common._unsubscribe_project_events


@asynccontextmanager
async def lifespan(_app: FastAPI):
    common.startup()
    yield


app = FastAPI(title="Ludens-Flow API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)

if common.STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(common.STATIC_DIR)), name="static")

app.include_router(events.router)
app.include_router(chat.router)
app.include_router(projects.router)
app.include_router(workspaces.router)
app.include_router(settings.router)
app.include_router(copywriting.router)


def _sync_common_test_overrides() -> None:
    """Keep legacy direct-call monkeypatches working after the router split."""
    if globals().get("graph_step") is not common.graph_step:
        common.graph_step = globals()["graph_step"]


def post_chat(req):
    _sync_common_test_overrides()
    return common.post_chat(req)


@app.get("/")
def index():
    index_file = common.WEB_DIST_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"message": "Ludens-Flow API. Build web frontend and mount static assets at /static."}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Ludens-Flow web API.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8011)
    args = parser.parse_args()

    import uvicorn

    uvicorn.run("ludens_flow.app.api:app", host=args.host, port=args.port, reload=False)


if __name__ == "__main__":
    main()
