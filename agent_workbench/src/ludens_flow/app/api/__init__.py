import argparse
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import chat, common, copywriting, events, game_model, projects, settings, workspaces
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
app.include_router(game_model.router)


def _sync_common_test_overrides() -> None:
    """Keep legacy direct-call monkeypatches working after the router split."""
    if globals().get("graph_step") is not common.graph_step:
        common.graph_step = globals()["graph_step"]
    if globals().get("graph_step") is not chat.graph_step:
        chat.graph_step = globals()["graph_step"]


def post_chat(req):
    _sync_common_test_overrides()
    return chat.post_chat(req)


get_state = chat.get_state
post_action = chat.post_action
post_reset = chat.post_reset

post_reset_current_project = projects.post_reset_current_project
get_projects = projects.get_projects
post_project = projects.post_project
select_project = projects.select_project
post_archive_project = projects.post_archive_project
post_rename_project = projects.post_rename_project
post_restore_project = projects.post_restore_project
delete_archived_project = projects.delete_archived_project
post_export_current_project = projects.post_export_current_project
post_import_project_bundle = projects.post_import_project_bundle

get_current_project_unity_binding = workspaces.get_current_project_unity_binding
post_current_project_unity_bind = workspaces.post_current_project_unity_bind
post_current_project_unity_unbind = workspaces.post_current_project_unity_unbind
get_current_project_workspaces = workspaces.get_current_project_workspaces
post_current_project_workspace = workspaces.post_current_project_workspace
delete_current_project_workspace = workspaces.delete_current_project_workspace
list_workspace_files = workspaces.list_workspace_files
get_workspace_file_content = workspaces.get_workspace_file_content
put_workspace_file_content = workspaces.put_workspace_file_content
import_gdd_fastdev = workspaces.import_gdd_fastdev
upload_workspace_file_asset = workspaces.upload_workspace_file_asset
get_workspace_note_asset = workspaces.get_workspace_note_asset

get_current_project_settings = settings.get_current_project_settings
post_current_project_settings = settings.post_current_project_settings
get_current_project_github = settings.get_current_project_github
post_current_project_github_bind = settings.post_current_project_github_bind
delete_current_project_github_bind = settings.delete_current_project_github_bind
get_model_profiles = settings.get_model_profiles
get_current_user_profile = settings.get_current_user_profile
post_current_user_profile = settings.post_current_user_profile
delete_current_project_mcp_connection = settings.delete_current_project_mcp_connection
post_check_current_project_mcp_connections = settings.post_check_current_project_mcp_connections
post_permission_decision = settings.post_permission_decision
get_tool_catalog = settings.get_tool_catalog
get_skill_catalog = settings.get_skill_catalog
post_import_skill = settings.post_import_skill
post_skill_draft = settings.post_skill_draft
delete_installed_skill = settings.delete_installed_skill
get_current_project_skills = settings.get_current_project_skills
post_current_project_skill_toggle = settings.post_current_project_skill_toggle

post_generate_current_project_copywriting = copywriting.post_generate_current_project_copywriting
post_create_current_project_copywriting_job = copywriting.post_create_current_project_copywriting_job
get_current_project_copywriting_job = copywriting.get_current_project_copywriting_job

GameModelGenerationRequest = game_model.GameModelGenerationRequest
GameModelRuntimeScenesRequest = game_model.GameModelRuntimeScenesRequest
GameModelRuntimeTestRequest = game_model.GameModelRuntimeTestRequest
GameModelExportRequest = game_model.GameModelExportRequest
get_current_project_game_model_runtime = game_model.get_current_project_game_model_runtime
post_current_project_game_model_runtime_scenes = game_model.post_current_project_game_model_runtime_scenes
post_current_project_game_model_behavior_tree = game_model.post_current_project_game_model_behavior_tree
post_current_project_game_model_questline = game_model.post_current_project_game_model_questline
post_current_project_game_model_multimodal_plan = game_model.post_current_project_game_model_multimodal_plan
post_current_project_game_model_runtime_test = game_model.post_current_project_game_model_runtime_test
post_current_project_game_model_export = game_model.post_current_project_game_model_export


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
