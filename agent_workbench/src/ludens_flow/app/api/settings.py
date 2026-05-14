from fastapi import APIRouter

from . import common as c

router = APIRouter()

router.get("/api/projects/current/settings")(c.get_current_project_settings)
router.post("/api/projects/current/settings")(c.post_current_project_settings)
router.get("/api/projects/current/github")(c.get_current_project_github)
router.post("/api/projects/current/github/bind")(c.post_current_project_github_bind)
router.delete("/api/projects/current/github/bind")(c.delete_current_project_github_bind)
router.get("/api/model-profiles")(c.get_model_profiles)
router.get("/api/projects/current/user-profile")(c.get_current_user_profile)
router.post("/api/projects/current/user-profile")(c.post_current_user_profile)
router.delete("/api/projects/current/mcp-connections/{connection_id}")(c.delete_current_project_mcp_connection)
router.post("/api/projects/current/mcp-connections/check")(c.post_check_current_project_mcp_connections)
router.post("/api/permissions/{request_id}/decision")(c.post_permission_decision)
router.get("/api/tools")(c.get_tool_catalog)
router.get("/api/skills")(c.get_skill_catalog)
router.post("/api/skills/import")(c.post_import_skill)
router.post("/api/skills/drafts")(c.post_skill_draft)
router.delete("/api/skills/{skill_id}")(c.delete_installed_skill)
router.get("/api/projects/current/skills")(c.get_current_project_skills)
router.post("/api/projects/current/skills/{skill_id}")(c.post_current_project_skill_toggle)

