import type {
  ProjectCreateResponse,
  ModelProfilesResponse,
  ProjectSettingsResponse,
  ProjectSelectResponse,
  ProjectsResponse,
  StateResponse,
} from "../types";
import { fetchJson } from "./http";

export function getProjects() {
  return fetchJson<ProjectsResponse>("/api/projects");
}

export function getCurrentProjectSettings() {
  return fetchJson<ProjectSettingsResponse>("/api/projects/current/settings");
}

export function getModelProfiles() {
  return fetchJson<ModelProfilesResponse>("/api/model-profiles");
}

export function updateCurrentProjectSettings(body: {
  agent_file_write_enabled?: boolean;
  agent_file_write_confirm_required?: boolean;
  model_routing?: Record<string, unknown>;
}) {
  return fetchJson<ProjectSettingsResponse>("/api/projects/current/settings", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function submitPermissionDecision(requestId: string, approved: boolean) {
  return fetchJson<{ permission_request_id: string; approved: boolean }>(
    `/api/permissions/${encodeURIComponent(requestId)}/decision`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ approved }),
    },
  );
}

export function createProject(body: {
  display_name?: string | null;
  title?: string | null;
}) {
  return fetchJson<ProjectCreateResponse>("/api/projects", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function selectProject(projectId: string) {
  return fetchJson<ProjectSelectResponse>(
    `/api/projects/${encodeURIComponent(projectId)}/select`,
    {
      method: "POST",
    },
  );
}

export function resetCurrentProject() {
  return fetchJson<StateResponse>("/api/projects/current/reset", {
    method: "POST",
  });
}

export function renameProject(projectId: string, display_name: string) {
  return fetchJson<ProjectsResponse>(
    `/api/projects/${encodeURIComponent(projectId)}/rename`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ display_name }),
    },
  );
}

export function archiveProject(projectId: string) {
  return fetchJson<ProjectsResponse>(
    `/api/projects/${encodeURIComponent(projectId)}/archive`,
    {
      method: "POST",
    },
  );
}

export function restoreProject(projectId: string, setActive = false) {
  return fetchJson<ProjectsResponse>(
    `/api/projects/${encodeURIComponent(projectId)}/restore`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ set_active: setActive }),
    },
  );
}

export function deleteProject(projectId: string) {
  return fetchJson<{
    deleted_project: string;
    active_project: string;
    active_projects: ProjectsResponse["active_projects"];
    archived_projects: ProjectsResponse["archived_projects"];
  }>(`/api/projects/${encodeURIComponent(projectId)}`, {
    method: "DELETE",
  });
}
