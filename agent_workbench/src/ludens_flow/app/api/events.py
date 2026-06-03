from fastapi import APIRouter

from . import common as c
from .common import *  # Reuse shared models, helpers, and capability imports.

for _name in dir(c):
    if _name.startswith("_") and not _name.startswith("__"):
        globals()[_name] = getattr(c, _name)

router = APIRouter()

async def stream_project_events(project_id: str):
    resolved_project_id = resolve_project_id(project_id)
    if not resolved_project_id:
        raise HTTPException(status_code=404, detail="Project not found")

    subscriber = _subscribe_project_events(resolved_project_id)

    async def event_stream():
        try:
            initial_state = st.load_state(project_id=resolved_project_id)
            yield _format_sse(
                _event_payload(
                    "connected",
                    project_id=resolved_project_id,
                    state=initial_state,
                    include_projects=True,
                )
            )

            while True:
                try:
                    payload = await asyncio.to_thread(subscriber.get, True, 15)
                except queue.Empty:
                    yield ": keep-alive\n\n"
                    continue
                yield _format_sse(payload)
        finally:
            _unsubscribe_project_events(resolved_project_id, subscriber)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


router.get("/api/projects/{project_id}/events")(stream_project_events)
