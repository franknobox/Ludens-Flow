import { AGENTS } from "./constants";
import type {
  AgentKey,
  ComposerAttachment,
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
  if (!project?.updated_at) {
    return "暂无活动";
  }

  const raw = String(project.updated_at).replace("T", " ").replace("Z", "").trim();
  const date = new Date(project.updated_at);
  if (isNaN(date.getTime())) {
    return raw || "暂无活动";
  }

  const diffMs = Date.now() - date.getTime();
  if (diffMs < 60 * 1000) {
    return "刚刚";
  }

  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  const hour = String(date.getHours()).padStart(2, "0");
  const minute = String(date.getMinutes()).padStart(2, "0");

  const now = new Date();
  if (year === now.getFullYear() && month === String(now.getMonth() + 1).padStart(2, "0") && day === String(now.getDate()).padStart(2, "0")) {
    return `${hour}:${minute}`;
  }

  return `${year}-${month}-${day} ${hour}:${minute}`;
}

export function transientMessageText(
  text: string,
  attachments: ComposerAttachment[],
): string {
  const clean = text.trim();
  const imageCount = attachments.filter((item) => item.kind === "image").length;
  const fileCount = attachments.filter((item) => item.kind === "file").length;
  const parts: string[] = [];
  if (imageCount) {
    parts.push(`${imageCount} image${imageCount > 1 ? "s" : ""}`);
  }
  if (fileCount) {
    parts.push(`${fileCount} file${fileCount > 1 ? "s" : ""}`);
  }
  const attachmentSummary = parts.length ? `[${parts.join(" + ")}]` : "";

  if (clean && attachmentSummary) return `${clean}\n${attachmentSummary}`;
  if (clean) return clean;
  if (attachmentSummary) return attachmentSummary;
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
