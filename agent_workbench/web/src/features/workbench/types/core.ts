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
