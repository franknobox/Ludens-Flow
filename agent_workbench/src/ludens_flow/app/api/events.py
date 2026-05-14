from fastapi import APIRouter

from . import common as c

router = APIRouter()

router.get("/api/projects/{project_id}/events")(c.stream_project_events)

