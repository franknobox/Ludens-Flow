from typing import Any, Optional
from ludens_flow.core.paths import touch_project, SUPPORTED_TARGET_ENGINES, resolve_project_id

PROJECT_UPDATE_TARGET_ENGINE_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "project_update_target_engine",
        "description": "Update the target engine setting for the current project. This changes the project's default engine context.",
        "parameters": {
            "type": "object",
            "properties": {
                "target_engine": {
                    "type": "string",
                    "description": f"The new target engine to set. Supported values: {', '.join(sorted(SUPPORTED_TARGET_ENGINES))}",
                },
            },
            "required": ["target_engine"],
        },
    },
}

def project_update_target_engine(
    target_engine: str,
    *,
    project_id: Optional[str] = None,
) -> str:
    if not target_engine:
        raise ValueError("target_engine cannot be empty.")
        
    resolved = resolve_project_id(project_id)
    if not resolved:
        raise ValueError("No active project found.")
        
    try:
        meta = touch_project(
            resolved, 
            target_engine=target_engine
        )
    except ValueError as e:
        raise RuntimeError(f"Failed to update target engine: {str(e)}")
    
    updated_engine = meta.get("target_engine", "")
    return f"Project target engine successfully updated to: {updated_engine}"
