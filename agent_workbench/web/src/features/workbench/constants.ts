import type { AgentDef } from "./types";

export const AGENTS: AgentDef[] = [
  { key: "design", name: "Dam / Design" },
  { key: "pm", name: "Pax / PM" },
  { key: "engineering", name: "Eon / Engineering" },
  { key: "review", name: "Revs / Review" },
];

export const PHASE_LABEL: Record<string, string> = {
  GDD_DISCUSS: "GDD 讨论",
  GDD_COMMIT: "GDD 定稿",
  PM_DISCUSS: "PM 讨论",
  PM_COMMIT: "PM 定稿",
  ENG_DISCUSS: "工程讨论",
  ENG_COMMIT: "工程定稿",
  REVIEW: "评审",
  POST_REVIEW_DECISION: "评审后决策",
  DEV_COACHING: "持续开发辅导",
};
