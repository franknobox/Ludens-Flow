from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ludens_flow.capabilities.game_model.runtime import (
    build_multimodal_plan,
    build_runtime_export,
    build_runtime_state,
    generate_behavior_tree,
    generate_questline,
    run_runtime_scene_test,
    save_runtime_scenes,
)
from ludens_flow.core.paths import resolve_project_id

router = APIRouter()


class GameModelGenerationRequest(BaseModel):
    scene_id: str | None = None
    scene: dict[str, Any] | None = None
    prompt: str | None = None
    context: str | None = None
    character_name: str | None = None
    goal: str | None = None
    traits: list[str] | None = None
    constraints: list[str] | None = None
    theme: str | None = None
    player_level: int | None = None
    region: str | None = None
    beats: list[str] | None = None
    purpose: str | None = None
    modalities: list[str] | None = None


class GameModelRuntimeScenesRequest(BaseModel):
    scenes: list[dict[str, Any]]


class GameModelRuntimeTestRequest(BaseModel):
    scene_id: str | None = None
    scene: dict[str, Any] | None = None
    input: str | None = None
    prompt: str | None = None
    test_input: str | None = None
    attachments: list[dict[str, Any]] | None = None
    live_model: bool = False


class GameModelExportRequest(BaseModel):
    scene_ids: list[str] | None = None
    scenes: list[dict[str, Any]] | None = None


def _request_payload(req: BaseModel, *, project_id: str) -> dict[str, Any]:
    if hasattr(req, "model_dump"):
        payload = req.model_dump(exclude_none=True)
    else:
        payload = req.dict(exclude_none=True)
    payload["project_id"] = project_id
    return payload


def get_current_project_game_model_runtime():
    project_id = resolve_project_id()
    return build_runtime_state(project_id=project_id)


def post_current_project_game_model_runtime_scenes(req: GameModelRuntimeScenesRequest):
    project_id = resolve_project_id()
    if not req.scenes:
        raise HTTPException(status_code=400, detail="At least one runtime scene is required.")
    return save_runtime_scenes(req.scenes, project_id=project_id)


def post_current_project_game_model_behavior_tree(req: GameModelGenerationRequest):
    project_id = resolve_project_id()
    return generate_behavior_tree(_request_payload(req, project_id=project_id))


def post_current_project_game_model_questline(req: GameModelGenerationRequest):
    project_id = resolve_project_id()
    return generate_questline(_request_payload(req, project_id=project_id))


def post_current_project_game_model_multimodal_plan(req: GameModelGenerationRequest):
    project_id = resolve_project_id()
    return build_multimodal_plan(_request_payload(req, project_id=project_id))


def post_current_project_game_model_runtime_test(req: GameModelRuntimeTestRequest):
    project_id = resolve_project_id()
    return run_runtime_scene_test(_request_payload(req, project_id=project_id))


def post_current_project_game_model_export(req: GameModelExportRequest):
    project_id = resolve_project_id()
    return build_runtime_export(_request_payload(req, project_id=project_id))


router.get("/api/projects/current/game-model/runtime")(get_current_project_game_model_runtime)
router.post("/api/projects/current/game-model/runtime/scenes")(post_current_project_game_model_runtime_scenes)
router.post("/api/projects/current/game-model/behavior-tree")(post_current_project_game_model_behavior_tree)
router.post("/api/projects/current/game-model/questline")(post_current_project_game_model_questline)
router.post("/api/projects/current/game-model/multimodal-plan")(post_current_project_game_model_multimodal_plan)
router.post("/api/projects/current/game-model/runtime/test")(post_current_project_game_model_runtime_test)
router.post("/api/projects/current/game-model/export")(post_current_project_game_model_export)
