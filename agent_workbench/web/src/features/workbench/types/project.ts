import type { StateResponse } from "./chat";

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

export interface ProjectsResponse {
  active_project: string;
  projects: ProjectMeta[];
  active_projects: ProjectMeta[];
  archived_projects: ProjectMeta[];
}

export interface ProjectCreateResponse {
  project: ProjectMeta;
  state: StateResponse;
}

export interface ProjectSelectResponse {
  active_project: string;
  state: StateResponse;
}

export interface ProjectWorkspacesResponse {
  project_id: string;
  workspace?: ProjectWorkspace | null;
  workspaces: ProjectWorkspace[];
}

export interface ProjectSettingsResponse {
  project_id: string;
  agent_file_write_enabled: boolean;
  agent_file_write_confirm_required?: boolean;
  model_routing?: Record<string, unknown>;
  mcp_connections?: McpConnectionConfig[];
}

export interface UserProfileResponse {
  project_id: string;
  path: string;
  content: string;
}

export interface ModelProfileSummary {
  id: string;
  provider?: string;
  base_url?: string;
  has_api_key?: boolean;
}

export interface ModelProfilesResponse {
  profiles: ModelProfileSummary[];
}

export type McpEngine = "unity" | "godot" | "blender" | "unreal";

export interface McpConnectionConfig {
  id: string;
  engine: McpEngine;
  label: string;
  command: string;
  args: string[];
  env?: Record<string, string>;
  enabled: boolean;
}

export interface McpConnectionStatus {
  id: string;
  engine: McpEngine;
  label: string;
  enabled: boolean;
  configured: boolean;
  status: "not_configured" | "configured" | "reachable" | "tools_loaded" | "failed";
  message?: string;
  tools: Array<{
    name: string;
    description?: string;
  }>;
  tool_count: number;
}

export interface McpConnectionCheckResponse {
  project_id: string;
  connections: McpConnectionStatus[];
}
