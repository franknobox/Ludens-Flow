import type {
  ChatResponse,
  ProjectsResponse,
  StateResponse,
  WorkspaceFileContent,
  WorkspaceFilesResponse,
} from "./types";

async function fetchJson<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(path, options);
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.detail || data.error || `Request failed: ${response.status}`);
  }
  return data as T;
}

export const workbenchApi = {
  getState() {
    return fetchJson<StateResponse>("/api/state");
  },

  getProjects() {
    return fetchJson<ProjectsResponse>("/api/projects");
  },

  getWorkspaceFiles() {
    return fetchJson<WorkspaceFilesResponse>("/api/workspace/files");
  },

  getWorkspaceFileContent(fileId: string) {
    return fetchJson<WorkspaceFileContent>(
      `/api/workspace/files/${encodeURIComponent(fileId)}/content`,
    );
  },

  postChat(body: { message: string; images?: string[] }) {
    return fetchJson<ChatResponse>("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  },

  postAction(action: string) {
    return fetchJson<ChatResponse>("/api/actions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action }),
    });
  },

  createProject(body: { project_id: string; display_name?: string | null }) {
    return fetchJson<{ project: { id: string } }>("/api/projects", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  },

  selectProject(projectId: string) {
    return fetchJson<{ active_project: string }>(
      `/api/projects/${encodeURIComponent(projectId)}/select`,
      {
        method: "POST",
      },
    );
  },

  resetCurrentProject() {
    return fetchJson<StateResponse>("/api/projects/current/reset", {
      method: "POST",
    });
  },
};
