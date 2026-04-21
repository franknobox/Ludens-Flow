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
  model_routing?: Record<string, unknown>;
}
