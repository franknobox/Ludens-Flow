import { AGENTS } from "./constants";
import type {
  AgentKey,
  HistoryByAgent,
  HistoryEntry,
  ProjectMeta,
  RenderMessage,
  WorkbenchStateModel,
} from "./types";

export function toErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  return String(error);
}

export function phaseToAgent(phase: string): AgentKey {
  if (!phase) return "design";
  if (phase.startsWith("GDD_")) return "design";
  if (phase.startsWith("PM_")) return "pm";
  if (phase.startsWith("ENG_") || phase === "DEV_COACHING") return "engineering";
  return "review";
}

export function normalizeAgent(agent: string | undefined, phase: string | undefined): AgentKey {
  const raw = String(agent || "").toLowerCase();
  if (raw.includes("design")) return "design";
  if (raw.includes("pm")) return "pm";
  if (raw.includes("engineer")) return "engineering";
  if (raw.includes("review")) return "review";
  return phaseToAgent(phase || "");
}

export function agentName(key: AgentKey): string {
  return AGENTS.find((item) => item.key === key)?.name || key;
}

export function projectUpdated(project: ProjectMeta | undefined): string {
  return project?.updated_at
    ? String(project.updated_at).replace("T", " ").replace("Z", "")
    : "No activity";
}

export function transientMessageText(text: string, imageCount: number): string {
  const clean = text.trim();
  if (clean && imageCount) return `${clean}\n[${imageCount} image${imageCount > 1 ? "s" : ""}]`;
  if (clean) return clean;
  if (imageCount) return `[${imageCount} image${imageCount > 1 ? "s" : ""}]`;
  return "";
}

function pushHistoryRow(rows: HistoryByAgent, key: AgentKey, item: RenderMessage) {
  rows[key].push(item);
}

export function buildHistoryByAgent(state: WorkbenchStateModel): HistoryByAgent {
  const rows: HistoryByAgent = {
    design: [],
    pm: [],
    engineering: [],
    review: [],
  };

  const transcript = state.transcript_history || [];
  if (transcript.length) {
    transcript.forEach((item: HistoryEntry) => {
      const key = normalizeAgent(item.agent, item.phase);
      pushHistoryRow(rows, key, {
        role: item.role,
        content: String(item.content || ""),
        phase: item.phase || state.phase,
      });
    });
    return rows;
  }

  const key = state.current_agent || phaseToAgent(state.phase);
  (state.chat_history || []).forEach((item) => {
    pushHistoryRow(rows, key, {
      role: item.role,
      content: String(item.content || ""),
      phase: state.phase,
    });
  });
  return rows;
}
