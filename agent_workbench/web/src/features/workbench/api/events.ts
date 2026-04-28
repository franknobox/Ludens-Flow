import type {
  ProjectMeta,
  StateResponse,
  WorkbenchEvent,
  WorkbenchEventType,
} from "../types";

const KNOWN_EVENT_TYPES = new Set<WorkbenchEventType>([
  "connected",
  "run_started",
  "permission_required",
  "permission_granted",
  "permission_denied",
  "tool_started",
  "tool_completed",
  "tool_failed",
  "tool_progress",
  "file_changed",
  "assistant_stream_started",
  "assistant_delta",
  "assistant_stream_completed",
  "state_updated",
  "run_failed",
  "projects_updated",
]);

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function asString(value: unknown): string | undefined {
  return typeof value === "string" ? value : undefined;
}

function asProjectMetaArray(value: unknown): ProjectMeta[] | undefined {
  if (!Array.isArray(value)) {
    return undefined;
  }
  return value.filter(isRecord) as unknown as ProjectMeta[];
}

function asStateResponse(value: unknown): StateResponse | undefined {
  if (!isRecord(value)) {
    return undefined;
  }
  return value as unknown as StateResponse;
}

export function normalizeWorkbenchEvent(
  raw: unknown,
  fallbackProjectId: string,
): WorkbenchEvent | null {
  if (!isRecord(raw)) {
    return null;
  }

  const type = asString(raw.type);
  if (!type || !KNOWN_EVENT_TYPES.has(type as WorkbenchEventType)) {
    return null;
  }

  return {
    type: type as WorkbenchEventType,
    timestamp: asString(raw.timestamp),
    project_id: asString(raw.project_id) || fallbackProjectId,
    state: asStateResponse(raw.state),
    active_project: asString(raw.active_project),
    projects: asProjectMetaArray(raw.projects),
    active_projects: asProjectMetaArray(raw.active_projects),
    archived_projects: asProjectMetaArray(raw.archived_projects),
    phase: asString(raw.phase),
    current_agent: asString(raw.current_agent) as WorkbenchEvent["current_agent"],
    message: asString(raw.message),
    delta: asString(raw.delta),
    error: asString(raw.error),
    tool_name: asString(raw.tool_name),
    tool_summary: asString(raw.tool_summary),
    tool_result_summary: asString(raw.tool_result_summary),
    workspace_id: asString(raw.workspace_id),
    file_path: asString(raw.file_path),
    change_type: asString(raw.change_type),
    permission_request_id: asString(raw.permission_request_id),
  };
}

export function openProjectEvents(
  projectId: string,
  onEvent: (event: WorkbenchEvent) => void,
  onError?: () => void,
) {
  const source = new EventSource(
    `/api/projects/${encodeURIComponent(projectId)}/events`,
  );

  source.onmessage = (event) => {
    try {
      const raw = JSON.parse(event.data) as unknown;
      const normalized = normalizeWorkbenchEvent(raw, projectId);
      if (normalized) {
        onEvent(normalized);
      }
    } catch {
      // ignore malformed payloads
    }
  };

  source.onerror = () => {
    if (onError) {
      onError();
    }
  };

  return source;
}
