from fastapi import APIRouter

from . import common as c

router = APIRouter()

router.get("/api/state")(c.get_state)
router.post("/api/chat")(c.post_chat)
router.post("/api/actions")(c.post_action)
router.post("/api/reset")(c.post_reset)

