import type { StateResponse } from "./chat";

export interface ToolCatalogItem {
  name: string;
  description: string;
  category: string;
  workspace_kind?: string | null;
  requires_workspace: boolean;
  writes_files: boolean;
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

export interface WorkspaceFileUpdateResponse extends WorkspaceFileContent {
  state?: StateResponse;
}

export interface WorkspaceFileAssetUploadResponse {
  file_id: string;
  name: string;
  url: string;
  markdown: string;
}

export interface ToolsResponse {
  tools: ToolCatalogItem[];
}

export interface WorkspaceFilesResponse {
  files: WorkspaceFileItem[];
}
