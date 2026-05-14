from fastapi import APIRouter

from . import common as c

router = APIRouter()

router.get("/api/projects/current/unity")(c.get_current_project_unity_binding)
router.post("/api/projects/current/unity/bind")(c.post_current_project_unity_bind)
router.post("/api/projects/current/unity/unbind")(c.post_current_project_unity_unbind)
router.get("/api/projects/current/workspaces")(c.get_current_project_workspaces)
router.post("/api/projects/current/workspaces")(c.post_current_project_workspace)
router.delete("/api/projects/current/workspaces/{workspace_id}")(c.delete_current_project_workspace)
router.get("/api/workspace/files")(c.list_workspace_files)
router.get("/api/workspace/files/{file_id}/content")(c.get_workspace_file_content)
router.put("/api/workspace/files/{file_id}/content")(c.put_workspace_file_content)
router.post("/api/workspace/files/gdd/import-fastdev")(c.import_gdd_fastdev)
router.post("/api/workspace/files/{file_id}/assets")(c.upload_workspace_file_asset)
router.get("/api/workspace/files/notes/assets/{asset_name}")(c.get_workspace_note_asset)

