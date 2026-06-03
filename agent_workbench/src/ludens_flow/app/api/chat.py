from fastapi import APIRouter

from . import common as c
from .common import *  # Reuse shared models, helpers, and capability imports.

for _name in dir(c):
    if _name.startswith("_") and not _name.startswith("__"):
        globals()[_name] = getattr(c, _name)

router = APIRouter()

def get_state():
    state = st.load_state()
    return _state_to_json(state)

def post_chat(req: ChatRequest):
    project_id = resolve_project_id()
    lock = _get_project_lock(project_id)
    user_message = req.message.strip()

    with lock:
        state = st.load_state(project_id=project_id)

        if user_message.lower().startswith("/unity bind "):
            unity_root = user_message[len("/unity bind ") :].strip().strip('"')
            try:
                meta = set_project_unity_root(unity_root, project_id=project_id)
                return {
                    "reply": f"Unity project bound: {meta.get('unity_root', '')}",
                    "phase": state.phase,
                    "error": None,
                    "needs_decision": bool(get_available_actions(state)),
                    "review_gate": state.review_gate,
                    "actions": get_available_actions(state),
                }
            except Exception as e:
                return {
                    "reply": "",
                    "phase": state.phase,
                    "error": str(e),
                    "needs_decision": bool(get_available_actions(state)),
                    "review_gate": state.review_gate,
                    "actions": get_available_actions(state),
                }

        if user_message.lower() == "/unity unbind":
            meta = clear_project_unity_root(project_id=project_id)
            return {
                "reply": f"Unity project unbound for {meta['id']}.",
                "phase": state.phase,
                "error": None,
                "needs_decision": bool(get_available_actions(state)),
                "review_gate": state.review_gate,
                "actions": get_available_actions(state),
            }

        payload = _build_user_input_payload(user_message, req.attachments)
        user_input = payload.user_input
        if not (isinstance(user_input, str) and user_input) and not (
            isinstance(user_input, list) and user_input
        ):
            return {
                "reply": "",
                "phase": state.phase,
                "error": "输入不能为空",
                "attachment_warnings": payload.warnings,
                "needs_decision": bool(get_available_actions(state)),
                "actions": get_available_actions(state),
            }

        try:
            stream_handler = _build_stream_handler(project_id, state)
            tool_event_handler = _build_tool_event_handler(project_id, state)
            _publish_project_event(
                project_id,
                _event_payload(
                    "run_started",
                    project_id=project_id,
                    state=state,
                    message=user_message or "[multimodal input]",
                ),
            )
            state = graph_step(
                state,
                user_input,
                stream_handler=stream_handler,
                tool_event_handler=tool_event_handler,
                mcp_mode=bool(req.mcp_mode),
            )
            reply = getattr(state, "last_assistant_message", "") or ""
            state.last_assistant_message = None
            st.save_state(state, project_id=project_id)
            actions = get_available_actions(state)
            if getattr(stream_handler, "has_started", lambda: False)():
                _publish_project_event(
                    project_id,
                    _event_payload(
                        "assistant_stream_completed",
                        project_id=project_id,
                        state=state,
                    ),
                )
            _publish_project_event(
                project_id,
                _event_payload(
                    "state_updated",
                    project_id=project_id,
                    state=state,
                    include_projects=True,
                ),
            )
            _maybe_create_self_skill_from_message(project_id, state, user_message)
            return {
                "reply": reply,
                "phase": state.phase,
                "error": getattr(state, "last_error"),
                "attachment_warnings": payload.warnings,
                "needs_decision": bool(actions),
                "review_gate": state.review_gate,
                "actions": actions,
            }
        except Exception as e:
            logger.exception("chat error")
            state.last_error = str(e)
            st.save_state(state, project_id=project_id)
            actions = get_available_actions(state)
            _publish_project_event(
                project_id,
                _event_payload(
                    "run_failed",
                    project_id=project_id,
                    state=state,
                    error=str(e),
                    include_projects=True,
                ),
            )
            return {
                "reply": "",
                "phase": state.phase,
                "error": str(e),
                "attachment_warnings": payload.warnings,
                "needs_decision": bool(actions),
                "actions": actions,
            }

def post_action(req: ActionRequest):
    project_id = resolve_project_id()
    lock = _get_project_lock(project_id)

    with lock:
        state = st.load_state(project_id=project_id)
        actions = get_available_actions(state)
        allowed_ids = {item["id"] for item in actions}
        action_id = req.action.strip().lower()

        if action_id not in allowed_ids:
            return {
                "reply": "",
                "phase": state.phase,
                "error": f"Invalid action '{req.action}' for current phase.",
                "needs_decision": bool(actions),
                "review_gate": state.review_gate,
                "actions": actions,
            }

        try:
            stream_handler = _build_stream_handler(project_id, state)
            tool_event_handler = _build_tool_event_handler(project_id, state)
            _publish_project_event(
                project_id,
                _event_payload(
                    "run_started",
                    project_id=project_id,
                    state=state,
                    message=f"[ACTION] {action_id}",
                ),
            )
            synthetic_input = action_user_input(action_id)
            state = graph_step(
                state,
                synthetic_input,
                explicit_action=action_id,
                stream_handler=stream_handler,
                tool_event_handler=tool_event_handler,
            )
            reply = getattr(state, "last_assistant_message", "") or ""
            state.last_assistant_message = None
            st.save_state(state, project_id=project_id)
            next_actions = get_available_actions(state)
            if getattr(stream_handler, "has_started", lambda: False)():
                _publish_project_event(
                    project_id,
                    _event_payload(
                        "assistant_stream_completed",
                        project_id=project_id,
                        state=state,
                    ),
                )
            _publish_project_event(
                project_id,
                _event_payload(
                    "state_updated",
                    project_id=project_id,
                    state=state,
                    include_projects=True,
                ),
            )
            return {
                "reply": reply,
                "phase": state.phase,
                "error": getattr(state, "last_error"),
                "needs_decision": bool(next_actions),
                "review_gate": state.review_gate,
                "actions": next_actions,
            }
        except Exception as e:
            logger.exception("action error")
            state.last_error = str(e)
            st.save_state(state, project_id=project_id)
            actions = get_available_actions(state)
            _publish_project_event(
                project_id,
                _event_payload(
                    "run_failed",
                    project_id=project_id,
                    state=state,
                    error=str(e),
                    include_projects=True,
                ),
            )
            return {
                "reply": "",
                "phase": state.phase,
                "error": str(e),
                "needs_decision": bool(actions),
                "review_gate": state.review_gate,
                "actions": actions,
            }

def post_reset():
    return post_reset_current_project()


router.get("/api/state")(get_state)
router.post("/api/chat")(post_chat)
router.post("/api/actions")(post_action)
router.post("/api/reset")(post_reset)
