import type { AgentDef } from "./types";

export const AGENTS: AgentDef[] = [
  { key: "design", name: "Dam / Design" },
  { key: "pm", name: "Pax / PM" },
  { key: "engineering", name: "Eon / Engineering" },
  { key: "review", name: "Revs / Review" },
];

export const PHASE_LABEL: Record<string, string> = {
  GDD_DISCUSS: "GDD Discuss",
  GDD_COMMIT: "GDD Commit",
  PM_DISCUSS: "PM Discuss",
  PM_COMMIT: "PM Commit",
  ENG_DISCUSS: "ENG Discuss",
  ENG_COMMIT: "ENG Commit",
  REVIEW: "Review",
  POST_REVIEW_DECISION: "Post Review Decision",
  DEV_COACHING: "Dev Coaching",
};
