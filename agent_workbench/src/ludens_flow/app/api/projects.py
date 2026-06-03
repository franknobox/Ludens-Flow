from fastapi import APIRouter

from . import common as c
from .common import *  # Reuse shared models, helpers, and capability imports.

for _name in dir(c):
    if _name.startswith("_") and not _name.startswith("__"):
        globals()[_name] = getattr(c, _name)

router = APIRouter()

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

def get_projects():
    return {
        "active_project": resolve_project_id(),
        "projects": list_projects(),
        "active_projects": list_active_projects(),
        "archived_projects": list_archived_projects(),
    }

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

def post_export_current_project(req: ProjectExportRequest):
    state = st.load_state()
    project_id = getattr(state, "project_id", None)
    bundle = st.export_project_bundle(req.output_path, project_id=project_id)
    return {
        "project_id": project_id,
        "bundle_path": str(bundle),
    }

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


router.post("/api/projects/current/reset")(post_reset_current_project)
router.get("/api/projects")(get_projects)
router.post("/api/projects")(post_project)
router.post("/api/projects/{project_id}/select")(select_project)
router.post("/api/projects/{project_id}/archive")(post_archive_project)
router.post("/api/projects/{project_id}/rename")(post_rename_project)
router.post("/api/projects/{project_id}/restore")(post_restore_project)
router.delete("/api/projects/{project_id}")(delete_archived_project)
router.post("/api/projects/current/export")(post_export_current_project)
router.post("/api/projects/import")(post_import_project_bundle)
