from fastapi import APIRouter

from . import common as c

router = APIRouter()

router.post("/api/projects/current/copywriting/generate")(c.post_generate_current_project_copywriting)
router.post("/api/projects/current/copywriting/jobs")(c.post_create_current_project_copywriting_job)
router.get("/api/projects/current/copywriting/jobs/{job_id}")(c.get_current_project_copywriting_job)

