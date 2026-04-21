// 文件功能：Workbench 前端 API 访问层，统一封装所有 HTTP 请求。
// 核心内容：提供状态、项目、会话、工作区文件与设置接口调用方法。
// 核心内容：统一请求错误解析与 SSE 事件订阅，减少页面层重复逻辑。

import type {
  ChatResponse,
  ComposerAttachment,
  ProjectCreateResponse,
  ProjectSettingsResponse,
  ProjectSelectResponse,
  ProjectsResponse,
  ProjectWorkspacesResponse,
  StateResponse,
  ToolsResponse,
  WorkbenchEvent,
  WorkspaceFileContent,
  WorkspaceFileUpdateResponse,
  WorkspaceFilesResponse,
} from "./types";

async function fetchJson<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(path, options);
  const raw = await response.text();
  let data: unknown = null;

  if (raw) {
    try {
      data = JSON.parse(raw) as unknown;
    } catch {
      data = raw;
    }
  }

  if (!response.ok) {
    if (data && typeof data === "object") {
      const payload = data as Record<string, unknown>;
      throw new Error(
        String(payload.detail || payload.error || `请求失败：${response.status}`),
      );
    }
    throw new Error(String(data || `请求失败：${response.status}`));
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

  updateWorkspaceFileContent(fileId: string, content: string) {
    return fetchJson<WorkspaceFileUpdateResponse>(
      `/api/workspace/files/${encodeURIComponent(fileId)}/content`,
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content }),
      },
    );
  },

  getCurrentWorkspaces() {
    return fetchJson<ProjectWorkspacesResponse>("/api/projects/current/workspaces");
  },

  getCurrentProjectSettings() {
    return fetchJson<ProjectSettingsResponse>("/api/projects/current/settings");
  },

  updateCurrentProjectSettings(body: {
    agent_file_write_enabled?: boolean;
    model_routing?: Record<string, unknown>;
  }) {
    return fetchJson<ProjectSettingsResponse>("/api/projects/current/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  },

  getTools() {
    return fetchJson<ToolsResponse>("/api/tools");
  },

  addCurrentWorkspace(body: {
    root: string;
    kind: string;
    label?: string | null;
    writable?: boolean;
    enabled?: boolean;
  }) {
    return fetchJson<ProjectWorkspacesResponse>("/api/projects/current/workspaces", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  },

  deleteCurrentWorkspace(workspaceId: string) {
    return fetchJson<ProjectWorkspacesResponse>(
      `/api/projects/current/workspaces/${encodeURIComponent(workspaceId)}`,
      {
        method: "DELETE",
      },
    );
  },

  postChat(body: {
    message: string;
    attachments?: Array<{
      kind: ComposerAttachment["kind"];
      name: string;
      mime_type: string;
      data_url: string;
      size: number;
    }>;
  }) {
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

  createProject(body: { display_name?: string | null; title?: string | null }) {
    return fetchJson<ProjectCreateResponse>("/api/projects", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  },

  selectProject(projectId: string) {
    return fetchJson<ProjectSelectResponse>(
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

  renameProject(projectId: string, display_name: string) {
    return fetchJson<ProjectsResponse>(
      `/api/projects/${encodeURIComponent(projectId)}/rename`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ display_name }),
      },
    );
  },

  archiveProject(projectId: string) {
    return fetchJson<ProjectsResponse>(
      `/api/projects/${encodeURIComponent(projectId)}/archive`,
      {
        method: "POST",
      },
    );
  },

  restoreProject(projectId: string, setActive = false) {
    return fetchJson<ProjectsResponse>(
      `/api/projects/${encodeURIComponent(projectId)}/restore`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ set_active: setActive }),
      },
    );
  },

  deleteProject(projectId: string) {
    return fetchJson<{
      deleted_project: string;
      active_project: string;
      active_projects: ProjectsResponse["active_projects"];
      archived_projects: ProjectsResponse["archived_projects"];
    }>(`/api/projects/${encodeURIComponent(projectId)}`, {
      method: "DELETE",
    });
  },

  openProjectEvents(
    projectId: string,
    onEvent: (event: WorkbenchEvent) => void,
    onError?: () => void,
  ) {
    const source = new EventSource(
      `/api/projects/${encodeURIComponent(projectId)}/events`,
    );

    source.onmessage = (event) => {
      try {
        onEvent(JSON.parse(event.data) as WorkbenchEvent);
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
  },
};
