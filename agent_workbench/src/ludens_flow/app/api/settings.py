from fastapi import APIRouter

from . import common as c
from .common import *  # Reuse shared models, helpers, and capability imports.

for _name in dir(c):
    if _name.startswith("_") and not _name.startswith("__"):
        globals()[_name] = getattr(c, _name)

router = APIRouter()

def get_current_project_settings():
    project_id = resolve_project_id()
    return get_project_settings(project_id=project_id)

def post_current_project_settings(req: ProjectSettingsRequest):
    project_id = resolve_project_id()
    if (
        req.agent_file_write_enabled is None
        and req.agent_file_write_confirm_required is None
        and req.skill_self_capture_enabled is None
        and req.model_routing is None
        and req.mcp_connections is None
        and req.target_engine is None
        and req.engine_profile is None
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

    if req.skill_self_capture_enabled is not None:
        set_project_skill_self_capture_enabled(
            req.skill_self_capture_enabled,
            project_id=project_id,
        )

    if req.model_routing is not None:
        set_project_model_routing(
            req.model_routing,
            project_id=project_id,
        )

    if req.target_engine is not None or req.engine_profile is not None:
        engine_settings = {"project_id": project_id}
        if req.target_engine is not None:
            engine_settings["target_engine"] = req.target_engine
        if req.engine_profile is not None:
            engine_settings["engine_profile"] = req.engine_profile
        try:
            set_project_engine_settings(**engine_settings)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    if req.mcp_connections is not None:
        existing_mcp_connections = get_project_mcp_connections(project_id=project_id)
        existing_mcp_ids = {
            str(item.get("id", ""))
            for item in existing_mcp_connections
            if str(item.get("id", "")).strip()
        }
        next_mcp_ids = {
            str(item.get("id", ""))
            for item in req.mcp_connections
            if str(item.get("id", "")).strip()
        }
        if (
            existing_mcp_ids
            and not existing_mcp_ids.issubset(next_mcp_ids)
            and not req.allow_clear_mcp_connections
        ):
            raise HTTPException(
                status_code=409,
                detail=(
                    "Refusing to remove existing MCP connections from the generic "
                    "settings endpoint. Use the explicit MCP delete endpoint."
                ),
            )
        set_project_mcp_connections(
            req.mcp_connections,
            project_id=project_id,
            allow_remove_mcp_connections=req.allow_clear_mcp_connections,
        )

    return get_project_settings(project_id=project_id)

def get_current_project_github():
    project_id = resolve_project_id()
    repo = get_project_github_repo(project_id=project_id)
    if not repo:
        return {
            "project_id": project_id,
            "configured": False,
            "repo": None,
            "summary": {},
            "branches": [],
            "commits": [],
            "pull_requests": [],
            "issues": [],
            "workflow_runs": [],
            "errors": [],
            "fetched_at": "",
            "auth": {"token_configured": False},
        }

    try:
        snapshot = fetch_github_snapshot(repo)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return {"project_id": project_id, **snapshot}

def post_current_project_github_bind(req: GithubRepoBindRequest):
    project_id = resolve_project_id()
    try:
        repo = parse_github_repo_ref(req.repo)
        set_project_github_repo(repo, project_id=project_id)
        snapshot = fetch_github_snapshot(repo)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return {"project_id": project_id, **snapshot}

def delete_current_project_github_bind():
    project_id = resolve_project_id()
    set_project_github_repo({}, project_id=project_id)
    return {
        "project_id": project_id,
        "configured": False,
        "repo": None,
        "summary": {},
        "branches": [],
        "commits": [],
        "pull_requests": [],
        "issues": [],
        "workflow_runs": [],
        "errors": [],
        "fetched_at": "",
        "auth": {"token_configured": False},
    }

def get_model_profiles():
    return {"profiles": list_model_profile_summaries()}

def get_current_user_profile():
    project_id = resolve_project_id()
    profile = read_profile_file(project_id=project_id)
    return {
        "project_id": project_id,
        "path": profile["path"],
        "display_path": _project_relative_profile_path(project_id),
        "content": profile["content"],
    }

def post_current_user_profile(req: UserProfileUpdateRequest):
    project_id = resolve_project_id()
    profile = write_profile_file(req.content, project_id=project_id)
    return {
        "project_id": project_id,
        "path": profile["path"],
        "display_path": _project_relative_profile_path(project_id),
        "content": profile["content"],
    }

def delete_current_project_mcp_connection(connection_id: str):
    project_id = resolve_project_id()
    connections = get_project_mcp_connections(project_id=project_id)
    next_connections = [
        item for item in connections if str(item.get("id", "")) != connection_id
    ]
    if len(next_connections) == len(connections):
        raise HTTPException(status_code=404, detail="MCP connection not found.")

    return set_project_mcp_connections(
        next_connections,
        project_id=project_id,
        allow_remove_mcp_connections=True,
    )

def post_check_current_project_mcp_connections(req: McpConnectionCheckRequest):
    project_id = resolve_project_id()
    connections = get_project_mcp_connections(project_id=project_id)

    if req.connection_id:
        connections = [
            item for item in connections if item.get("id") == req.connection_id
        ]
    if req.engine:
        engine = "unreal" if req.engine == "ue" else req.engine
        connections = [
            item for item in connections if item.get("engine") == engine
        ]

    return {
        "project_id": project_id,
        "connections": check_mcp_connections(connections),
    }

def post_permission_decision(request_id: str, req: PermissionDecisionRequest):
    with _PERMISSION_REQUESTS_GUARD:
        record = _PERMISSION_REQUESTS.get(request_id)
    if not record:
        raise HTTPException(status_code=404, detail="Permission request not found.")

    record["approved"] = bool(req.approved)
    record["event"].set()
    return {"permission_request_id": request_id, "approved": bool(req.approved)}

def get_tool_catalog():
    return {
        "tools": list_common_tools(),
    }

def get_skill_catalog():
    return {"skills": list_skills()}

def post_import_skill(req: SkillImportRequest):
    try:
        if req.github_url:
            skill = import_external_skill_github(req.github_url)
        elif req.zip_data_url:
            skill = import_external_skill_zip(req.zip_data_url)
        elif req.files:
            skill = import_external_skill_bundle(req.files)
        elif req.manifest is not None:
            skill = import_external_skill(req.manifest, prompt=req.prompt)
        else:
            raise ValueError("Skill import requires manifest, files, zip_data_url, or github_url.")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"skill": skill, "skills": list_skills()}

def post_skill_draft(req: SkillDraftRequest):
    project_id = resolve_project_id()
    try:
        skill = create_skill_draft(
            req.manifest,
            prompt=req.prompt,
            project_id=project_id,
            source_agent=req.source_agent,
            reason=req.reason,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"self_skill": skill}

def delete_installed_skill(skill_id: str):
    try:
        deleted = delete_skill(skill_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"deleted_skill": deleted, "skills": list_skills()}

def get_current_project_skills():
    project_id = resolve_project_id()
    return get_project_skills(project_id)

def post_current_project_skill_toggle(skill_id: str, req: ProjectSkillToggleRequest):
    project_id = resolve_project_id()
    try:
        return set_project_skill_enabled(
            skill_id,
            req.enabled,
            project_id=project_id,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


router.get("/api/projects/current/settings")(get_current_project_settings)
router.post("/api/projects/current/settings")(post_current_project_settings)
router.get("/api/projects/current/github")(get_current_project_github)
router.post("/api/projects/current/github/bind")(post_current_project_github_bind)
router.delete("/api/projects/current/github/bind")(delete_current_project_github_bind)
router.get("/api/model-profiles")(get_model_profiles)
router.get("/api/projects/current/user-profile")(get_current_user_profile)
router.post("/api/projects/current/user-profile")(post_current_user_profile)
router.delete("/api/projects/current/mcp-connections/{connection_id}")(delete_current_project_mcp_connection)
router.post("/api/projects/current/mcp-connections/check")(post_check_current_project_mcp_connections)
router.post("/api/permissions/{request_id}/decision")(post_permission_decision)
router.get("/api/tools")(get_tool_catalog)
router.get("/api/skills")(get_skill_catalog)
router.post("/api/skills/import")(post_import_skill)
router.post("/api/skills/drafts")(post_skill_draft)
router.delete("/api/skills/{skill_id}")(delete_installed_skill)
router.get("/api/projects/current/skills")(get_current_project_skills)
router.post("/api/projects/current/skills/{skill_id}")(post_current_project_skill_toggle)
