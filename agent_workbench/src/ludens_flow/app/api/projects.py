from fastapi import APIRouter

from . import common as c

router = APIRouter()

router.post("/api/projects/current/reset")(c.post_reset_current_project)
router.get("/api/projects")(c.get_projects)
router.post("/api/projects")(c.post_project)
router.post("/api/projects/{project_id}/select")(c.select_project)
router.post("/api/projects/{project_id}/archive")(c.post_archive_project)
router.post("/api/projects/{project_id}/rename")(c.post_rename_project)
router.post("/api/projects/{project_id}/restore")(c.post_restore_project)
router.delete("/api/projects/{project_id}")(c.delete_archived_project)
router.post("/api/projects/current/export")(c.post_export_current_project)
router.post("/api/projects/import")(c.post_import_project_bundle)

