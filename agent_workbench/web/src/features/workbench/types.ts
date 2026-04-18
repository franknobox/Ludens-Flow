export type AgentKey = "design" | "pm" | "engineering" | "review";

export interface AgentDef {
  key: AgentKey;
  name: string;
}

export interface WorkflowAction {
  id: string;
  label: string;
  description?: string;
}

export interface ProjectMeta {
  id: string;
  display_name?: string;
  title?: string;
  archived?: boolean;
  updated_at?: string;
  created_at?: string;
  last_phase?: string;
  last_message_preview?: string;
  unity_root?: string;
}

export interface ProjectWorkspace {
  id: string;
  label: string;
  kind: string;
  root: string;
  writable: boolean;
  enabled: boolean;
  source?: string;
}

export interface WorkspaceFileItem {
  id: string;
  name: string;
  artifact: string;
}

export interface WorkspaceFileContent {
  id: string;
  name: string;
  content: string;
}

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
  type: "tool_started" | "tool_completed" | "tool_failed";
  tool_name: string;
  tool_summary: string;
  tool_result_summary?: string;
  error?: string;
}

export interface WorkbenchEvent {
  type:
    | "connected"
    | "run_started"
    | "tool_started"
    | "tool_completed"
    | "tool_failed"
    | "assistant_stream_started"
    | "assistant_delta"
    | "assistant_stream_completed"
    | "state_updated"
    | "run_failed"
    | "projects_updated";
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
}

export interface ProjectsResponse {
  active_project: string;
  projects: ProjectMeta[];
  active_projects: ProjectMeta[];
  archived_projects: ProjectMeta[];
}

export interface ProjectWorkspacesResponse {
  project_id: string;
  workspace?: ProjectWorkspace | null;
  workspaces: ProjectWorkspace[];
}

export interface WorkspaceFilesResponse {
  files: WorkspaceFileItem[];
}

export interface ViewStateAgent {
  type: "agent";
  id: AgentKey;
}

export interface ViewStateFile {
  type: "file";
  id: string;
}

export type ViewState = ViewStateAgent | ViewStateFile;

export interface RenderMessage {
  role: string;
  content: string;
  phase?: string;
  thinking?: boolean;
}

export interface TransientChat {
  agentKey: AgentKey;
  phase: string;
  userText: string;
  thinking: boolean;
  assistantText?: string;
  toolEvents?: ToolProgressEvent[];
}

export interface WorkbenchStateModel {
  project_id: string;
  phase: string;
  current_agent: AgentKey;
  iteration_count: number;
  artifact_frozen: boolean;
  review_gate: Record<string, unknown> | null;
  transcript_history: HistoryEntry[];
  chat_history: HistoryEntry[];
  files: WorkspaceFileItem[];
  projects: ProjectMeta[];
  active_projects: ProjectMeta[];
  archived_projects: ProjectMeta[];
  actions: WorkflowAction[];
}

export type HistoryByAgent = Record<AgentKey, RenderMessage[]>;
