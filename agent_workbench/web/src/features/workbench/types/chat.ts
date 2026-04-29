import type { AgentKey, WorkflowAction } from "./core";
import type { ProjectMeta } from "./project";

export type ComposerAttachmentKind = "image" | "file";

export interface ComposerAttachment {
  id: string;
  kind: ComposerAttachmentKind;
  name: string;
  mimeType: string;
  size: number;
  dataUrl: string;
  previewUrl?: string;
}

export interface HistoryEntry {
  role: string;
  content: string;
  phase?: string;
  agent?: string;
}

export interface StateResponse {
  project_id: string;
  phase: string;
  current_agent: AgentKey;
  iteration_count: number;
  artifact_frozen: boolean;
  review_gate: Record<string, unknown> | null;
  transcript_history: HistoryEntry[];
  chat_history: HistoryEntry[];
  last_assistant_message?: string | null;
  last_error?: string | null;
  actions: WorkflowAction[];
}

export interface ChatResponse {
  reply: string;
  phase: string;
  error?: string | null;
  attachment_warnings?: string[];
  needs_decision?: boolean;
  review_gate?: Record<string, unknown> | null;
  actions?: WorkflowAction[];
}

export interface ToolProgressEvent {
  id: string;
  type:
    | "permission_required"
    | "permission_granted"
    | "permission_denied"
    | "tool_started"
    | "tool_progress"
    | "file_changed"
    | "tool_completed"
    | "tool_failed";
  tool_name: string;
  tool_summary: string;
  tool_result_summary?: string;
  message?: string;
  file_path?: string;
  change_type?: string;
  permission_request_id?: string;
  error?: string;
}

export type WorkbenchEventType =
  | "connected"
  | "run_started"
  | "permission_required"
  | "permission_granted"
  | "permission_denied"
  | "tool_started"
  | "tool_completed"
  | "tool_failed"
  | "tool_progress"
  | "file_changed"
  | "assistant_stream_started"
  | "assistant_delta"
  | "assistant_stream_completed"
  | "state_updated"
  | "run_failed"
  | "projects_updated";

export interface WorkbenchEvent {
  type: WorkbenchEventType;
  timestamp?: string;
  project_id?: string;
  state?: StateResponse;
  active_project?: string;
  projects?: ProjectMeta[];
  active_projects?: ProjectMeta[];
  archived_projects?: ProjectMeta[];
  phase?: string;
  current_agent?: AgentKey;
  message?: string;
  delta?: string;
  error?: string;
  tool_name?: string;
  tool_summary?: string;
  tool_result_summary?: string;
  workspace_id?: string;
  file_path?: string;
  change_type?: string;
  permission_request_id?: string;
}
