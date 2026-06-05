from fastapi import APIRouter

from . import common as c
from .common import *  # Reuse shared models, helpers, and capability imports.

for _name in dir(c):
    if _name.startswith("_") and not _name.startswith("__"):
        globals()[_name] = getattr(c, _name)

router = APIRouter()

def post_generate_current_project_copywriting(req: DesignCopywritingGenerateRequest):
    state = st.load_state()
    project_id = resolve_project_id(getattr(state, "project_id", None))
    request_data = req.dict()
    normalized_request = normalize_design_copywriting_request(request_data)
    response = generate_design_copywriting(
        normalized_request,
        project_id=project_id,
        external_references=request_data.get("external_references"),
    )
    return response.to_dict()

def post_create_current_project_copywriting_job(req: DesignCopywritingGenerateRequest):
    state = st.load_state()
    project_id = resolve_project_id(getattr(state, "project_id", None))
    request_data = req.dict()
    normalized_request = normalize_design_copywriting_request(request_data)
    request_data.update(normalized_request.to_dict())

    job_id = uuid.uuid4().hex
    _set_copywriting_job(
        job_id,
        {
            "job_id": job_id,
            "project_id": project_id,
            "status": "queued",
            "message": "文案生成任务已创建。",
            "request": normalized_request.to_dict(),
        },
    )
    _publish_copywriting_job_event(
        project_id,
        job_id,
        "copywriting_job_queued",
        status="queued",
        message="文案生成任务已创建。",
    )

    worker = threading.Thread(
        target=_run_copywriting_job,
        args=(job_id, project_id, request_data),
        daemon=True,
    )
    worker.start()
    return DesignCopywritingJobCreateResponse(job_id=job_id).dict()

def get_current_project_copywriting_job(job_id: str):
    state = st.load_state()
    project_id = resolve_project_id(getattr(state, "project_id", None))
    job = _get_copywriting_job(job_id)
    if not job or job.get("project_id") != project_id:
        raise HTTPException(status_code=404, detail="Copywriting job not found.")
    return job


router.post("/api/projects/current/copywriting/generate")(post_generate_current_project_copywriting)
router.post("/api/projects/current/copywriting/jobs")(post_create_current_project_copywriting_job)
router.get("/api/projects/current/copywriting/jobs/{job_id}")(get_current_project_copywriting_job)
