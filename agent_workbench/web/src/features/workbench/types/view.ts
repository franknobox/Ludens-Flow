import type { AgentKey } from "./core";
import type { HistoryEntry, ToolProgressEvent } from "./chat";
import type { ProjectMeta } from "./project";
import type { WorkspaceFileItem } from "./workspace";
import type { WorkflowAction } from "./core";

export interface ViewStateAgent {
  type: "agent";
  id: AgentKey;
}

export interface ViewStateFile {
  type: "file";
  id: string;
}

export interface ViewStateGithub {
  type: "github";
}

export interface ViewStateAigc {
  type: "aigc";
}

export interface ViewStateCopywriting {
  type: "copywriting";
}

export interface ViewStateGameModel {
  type: "game-model";
}

export interface ViewStateSkills {
  type: "skills";
}

export type McpTool = "unity" | "godot" | "ue" | "blender";

export interface ViewStateMcp {
  type: "mcp";
  tool: McpTool;
}

export type ViewState =
  | ViewStateAgent
  | ViewStateFile
  | ViewStateGithub
  | ViewStateAigc
  | ViewStateCopywriting
  | ViewStateGameModel
  | ViewStateSkills
  | ViewStateMcp;

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
