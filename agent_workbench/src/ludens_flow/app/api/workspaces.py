from fastapi import APIRouter

from . import common as c
from .common import *  # Reuse shared models, helpers, and capability imports.

for _name in dir(c):
    if _name.startswith("_") and not _name.startswith("__"):
        globals()[_name] = getattr(c, _name)

router = APIRouter()

def get_current_project_unity_binding():
    project_id = resolve_project_id()
    unity_root = get_project_unity_root(project_id)
    exists = bool(unity_root and Path(unity_root).exists())
    workspaces = list_project_workspaces(project_id=project_id, kind="unity")
    return {
        "project_id": project_id,
        "unity_root": unity_root,
        "bound": bool(unity_root),
        "exists": exists,
        "workspaces": workspaces,
    }

def post_current_project_unity_bind(req: UnityBindRequest):
    project_id = resolve_project_id()
    meta = set_project_unity_root(req.unity_root, project_id=project_id)
    return {
        "project_id": project_id,
        "unity_root": meta.get("unity_root", ""),
        "bound": bool(meta.get("unity_root", "")),
        "workspaces": meta.get("workspaces", []),
    }

def post_current_project_unity_unbind():
    project_id = resolve_project_id()
    meta = clear_project_unity_root(project_id=project_id)
    return {
        "project_id": project_id,
        "unity_root": meta.get("unity_root", ""),
        "bound": False,
        "workspaces": meta.get("workspaces", []),
    }

def get_current_project_workspaces():
    project_id = resolve_project_id()
    return {
        "project_id": project_id,
        "workspaces": list_project_workspaces(project_id=project_id, include_disabled=True),
    }

def post_current_project_workspace(req: ProjectWorkspaceRequest):
    project_id = resolve_project_id()
    try:
        meta = add_project_workspace(
            req.root,
            project_id=project_id,
            kind=req.kind,
            workspace_id=req.workspace_id,
            label=req.label,
            writable=req.writable,
            enabled=req.enabled,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    workspaces = meta.get("workspaces", [])
    normalized_root = str(Path(req.root).expanduser().resolve())
    added_workspace = next(
        (
            item
            for item in workspaces
            if item.get("root") == normalized_root and item.get("kind") == req.kind.lower()
        ),
        None,
    )
    return {
        "project_id": project_id,
        "workspace": added_workspace,
        "workspaces": workspaces,
    }

def delete_current_project_workspace(workspace_id: str):
    project_id = resolve_project_id()
    try:
        meta = remove_project_workspace(workspace_id, project_id=project_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "project_id": project_id,
        "workspaces": meta.get("workspaces", []),
    }

def list_workspace_files():
    return {"files": WORKSPACE_FILES}

def get_workspace_file_content(file_id: str):
    state = st.load_state()
    for f in WORKSPACE_FILES:
        if f["id"] == file_id:
            try:
                content = read_artifact(
                    f["artifact"], project_id=getattr(state, "project_id", None)
                )
                return {"id": file_id, "name": f["name"], "content": content}
            except Exception as e:
                logger.warning(f"Read artifact {file_id}: {e}")
                return {"id": file_id, "name": f["name"], "content": ""}
    raise HTTPException(status_code=404, detail="Not found")

def put_workspace_file_content(file_id: str, req: WorkspaceFileUpdateRequest):
    state = st.load_state()
    project_id = resolve_project_id(getattr(state, "project_id", None))

    for f in WORKSPACE_FILES:
        if f["id"] != file_id:
            continue

        try:
            write_artifact(
                f["artifact"],
                req.content,
                reason="Manual edit from workbench",
                actor=f["owner"],
                state=state,
                project_id=project_id,
                ignore_frozen=True,
            )
            st.save_state(state, project_id=project_id)
            updated_content = read_artifact(f["artifact"], project_id=project_id)
        except PermissionError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        except RuntimeError as e:
            raise HTTPException(status_code=409, detail=str(e)) from e
        except Exception as e:
            logger.warning(f"Write artifact {file_id}: {e}")
            raise HTTPException(status_code=500, detail="保存工件失败") from e

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
            "id": file_id,
            "name": f["name"],
            "content": updated_content,
            "state": _state_to_json(state),
        }

    raise HTTPException(status_code=404, detail="Not found")

def import_gdd_fastdev(req: GddFastDevImportRequest):
    project_id = resolve_project_id()
    lock = _get_project_lock(project_id)

    if not req.attachments:
        raise HTTPException(status_code=400, detail="请选择一个可读取的 GDD 文件")

    try:
        with lock:
            state = st.load_state(project_id=project_id)
            _publish_fastdev_event(
                project_id,
                state,
                "fastdev_started",
                "正在解析 GDD 文件...",
                status="running",
                step="gdd",
            )
            name, _mime_type, text = extract_attachment_text(req.attachments[0])
            gdd_markdown = _imported_gdd_markdown(name, text, req.project_info)

            state.artifact_frozen = False
            state.phase = Phase.PM_COMMIT.value
            state.last_error = None
            write_artifact(
                "GDD",
                gdd_markdown,
                reason="Imported GDD for fast development",
                actor="DesignAgent",
                state=state,
                project_id=project_id,
                ignore_frozen=True,
            )
            state.last_event = "GDD_COMMITTED"
            st.save_state(state, project_id=project_id)

        pm_agent = PMAgent()
        eng_agent = EngineeringAgent()
        review_agent = ReviewAgent()
        _apply_agent_prompt_template(pm_agent, "pm_agent.md")
        _apply_agent_prompt_template(eng_agent, "engineering_agent.md")
        _apply_agent_prompt_template(review_agent, "review_agent.md")
        user_persona = format_profile_for_prompt(read_profile_file(project_id))

        _publish_fastdev_event(
            project_id,
            state,
            "fastdev_progress",
            "正在生成 PROJECT_PLAN.md...",
            status="running",
            step="pm",
        )
        pm_result = pm_agent.commit(
            state,
            "快速开发模式：请直接基于导入的 GDD 生成项目计划。",
            user_persona=user_persona,
        )
        with lock:
            _commit_agent_artifact(project_id, state, pm_result, "PMAgent")
            state.phase = Phase.ENG_COMMIT.value
            st.save_state(state, project_id=project_id)

        _publish_fastdev_event(
            project_id,
            state,
            "fastdev_progress",
            "正在生成 IMPLEMENTATION_PLAN.md...",
            status="running",
            step="eng",
        )
        eng_result = eng_agent.plan_commit(
            state,
            "快速开发模式：请基于导入 GDD 和项目计划直接生成工程实施方案。",
            user_persona=user_persona,
        )
        with lock:
            _commit_agent_artifact(project_id, state, eng_result, "EngineeringAgent")
            state.phase = Phase.REVIEW.value
            st.save_state(state, project_id=project_id)

        _publish_fastdev_event(
            project_id,
            state,
            "fastdev_progress",
            "正在生成 REVIEW_REPORT.md...",
            status="running",
            step="review",
        )
        review_result = review_agent.commit(
            state,
            "快速开发模式：请完成自动评审，给出是否可以进入持续开发的判断。",
            user_persona=user_persona,
        )
        with lock:
            _commit_agent_artifact(project_id, state, review_result, "ReviewAgent")
            state.phase = Phase.DEV_COACHING.value
            state.artifact_frozen = True
            state.last_assistant_message = "快速开发工件已生成，已进入持续开发模式。"
            st.save_state(state, project_id=project_id)

        _publish_fastdev_event(
            project_id,
            state,
            "fastdev_completed",
            "快速开发工件已生成，点击确定进入持续开发。",
            status="completed",
            step="done",
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
            "state": _state_to_json(state),
            "gdd_content": read_artifact("GDD", project_id=project_id),
            "message": "快速开发工件已生成，已进入持续开发模式。",
        }
    except Exception as exc:
        logger.exception("fast development import failed")
        with lock:
            state = st.load_state(project_id=project_id)
            state.last_error = str(exc)
            st.save_state(state, project_id=project_id)
        _publish_fastdev_event(
            project_id,
            state,
            "fastdev_failed",
            "快速开发生成失败。",
            status="failed",
            step="failed",
        )
        _publish_project_event(
            project_id,
            _event_payload(
                "run_failed",
                project_id=project_id,
                state=state,
                error=str(exc),
                include_projects=True,
            ),
        )
        raise HTTPException(status_code=400, detail=str(exc)) from exc

def upload_workspace_file_asset(file_id: str, req: WorkspaceFileAssetUploadRequest):
    if file_id != "notes":
        raise HTTPException(status_code=400, detail="Assets are only supported for NOTES.md.")

    state = st.load_state()
    project_id = resolve_project_id(getattr(state, "project_id", None))
    data_url = str(req.data_url or "")
    if not data_url.startswith("data:") or ";base64," not in data_url:
        raise HTTPException(status_code=400, detail="Invalid image data URL.")

    header, encoded = data_url.split(";base64,", 1)
    mime_type = header[5:].split(";", 1)[0].lower()
    extension = _NOTE_ASSET_MIME_EXTENSIONS.get(mime_type)
    if not extension:
        raise HTTPException(status_code=400, detail=f"Unsupported image type: {mime_type}")

    try:
        payload = base64.b64decode(encoded, validate=True)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid base64 image data.") from exc

    max_bytes = 8 * 1024 * 1024
    if len(payload) > max_bytes:
        raise HTTPException(status_code=413, detail="Image is larger than 8 MB.")

    assets_dir = get_dev_notes_assets_dir(project_id)
    assets_dir.mkdir(parents=True, exist_ok=True)
    filename = _safe_note_asset_name(req.name, extension)
    target = assets_dir / filename
    target.write_bytes(payload)

    markdown = f"![{Path(filename).stem}](/api/workspace/files/notes/assets/{filename})"
    return {
        "file_id": file_id,
        "name": filename,
        "url": f"/api/workspace/files/notes/assets/{filename}",
        "markdown": markdown,
    }

def get_workspace_note_asset(asset_name: str):
    safe_name = Path(asset_name).name
    if safe_name != asset_name:
        raise HTTPException(status_code=400, detail="Invalid asset name.")

    state = st.load_state()
    project_id = resolve_project_id(getattr(state, "project_id", None))
    target = get_dev_notes_assets_dir(project_id) / safe_name
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="Asset not found.")
    return FileResponse(target)


router.get("/api/projects/current/unity")(get_current_project_unity_binding)
router.post("/api/projects/current/unity/bind")(post_current_project_unity_bind)
router.post("/api/projects/current/unity/unbind")(post_current_project_unity_unbind)
router.get("/api/projects/current/workspaces")(get_current_project_workspaces)
router.post("/api/projects/current/workspaces")(post_current_project_workspace)
router.delete("/api/projects/current/workspaces/{workspace_id}")(delete_current_project_workspace)
router.get("/api/workspace/files")(list_workspace_files)
router.get("/api/workspace/files/{file_id}/content")(get_workspace_file_content)
router.put("/api/workspace/files/{file_id}/content")(put_workspace_file_content)
router.post("/api/workspace/files/gdd/import-fastdev")(import_gdd_fastdev)
router.post("/api/workspace/files/{file_id}/assets")(upload_workspace_file_asset)
router.get("/api/workspace/files/notes/assets/{asset_name}")(get_workspace_note_asset)
