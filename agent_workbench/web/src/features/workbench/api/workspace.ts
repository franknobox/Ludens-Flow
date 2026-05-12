import type {
  ProjectWorkspacesResponse,
  GddFastDevImportResponse,
  WorkspaceFileAssetUploadResponse,
  WorkspaceFileContent,
  WorkspaceFilesResponse,
  WorkspaceFileUpdateResponse,
} from "../types";
import { fetchJson } from "./http";

export function getWorkspaceFiles() {
  return fetchJson<WorkspaceFilesResponse>("/api/workspace/files");
}

export function getWorkspaceFileContent(fileId: string) {
  return fetchJson<WorkspaceFileContent>(
    `/api/workspace/files/${encodeURIComponent(fileId)}/content`,
  );
}

export function updateWorkspaceFileContent(fileId: string, content: string) {
  return fetchJson<WorkspaceFileUpdateResponse>(
    `/api/workspace/files/${encodeURIComponent(fileId)}/content`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content }),
    },
  );
}

export function uploadWorkspaceFileAsset(fileId: string, body: {
  name: string;
  data_url: string;
}) {
  return fetchJson<WorkspaceFileAssetUploadResponse>(
    `/api/workspace/files/${encodeURIComponent(fileId)}/assets`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    },
  );
}

export function importGddFastDev(body: {
  attachments: Array<{
    kind: "file";
    name: string;
    mime_type: string;
    data_url: string;
    size: number;
  }>;
  project_info?: Record<string, string>;
}) {
  return fetchJson<GddFastDevImportResponse>(
    "/api/workspace/files/gdd/import-fastdev",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    },
  );
}

export function getCurrentWorkspaces() {
  return fetchJson<ProjectWorkspacesResponse>("/api/projects/current/workspaces");
}

export function addCurrentWorkspace(body: {
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
}

export function deleteCurrentWorkspace(workspaceId: string) {
  return fetchJson<ProjectWorkspacesResponse>(
    `/api/projects/current/workspaces/${encodeURIComponent(workspaceId)}`,
    {
      method: "DELETE",
    },
  );
}
