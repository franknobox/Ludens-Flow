import { fetchJson } from "../workbench/api/http";
import type {
  ProjectSkillsResponse,
  SkillAgentScope,
  SkillCatalogResponse,
  SkillManifest,
} from "./types";

const AGENT_SCOPES: SkillAgentScope[] = ["design", "pm", "engineering", "review"];

function slugify(value: string): string {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9\u4e00-\u9fa5]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function normalizeAgents(value: unknown): SkillAgentScope[] {
  if (!Array.isArray(value)) return ["engineering"];
  const agents = value
    .map((item) => String(item))
    .filter((item): item is SkillAgentScope =>
      AGENT_SCOPES.includes(item as SkillAgentScope),
    );
  return agents.length ? agents : ["engineering"];
}

function normalizeTags(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value
    .map((item) => String(item).trim())
    .filter(Boolean)
    .slice(0, 12);
}

export function normalizeSkillManifest(raw: unknown): SkillManifest {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) {
    throw new Error("skill.json 必须是一个 JSON 对象。");
  }
  const data = raw as Record<string, unknown>;
  const name = String(data.name || "").trim();
  if (!name) {
    throw new Error("skill.json 缺少 name。");
  }
  return {
    id: String(data.id || slugify(name) || `skill-${Date.now().toString(36)}`).trim(),
    name,
    description: String(data.description || "外部导入的 Skill 能力包。").trim(),
    version: String(data.version || "0.1.0").trim(),
    source: "external",
    agents: normalizeAgents(data.agents || data.scope),
    tags: normalizeTags(data.tags),
    updated_at: new Date().toISOString(),
  };
}

export function getSkillsCatalog(): Promise<SkillCatalogResponse> {
  return fetchJson<SkillCatalogResponse>("/api/skills");
}

export function getProjectSkills(_projectId: string): Promise<ProjectSkillsResponse> {
  return fetchJson<ProjectSkillsResponse>("/api/projects/current/skills");
}

export function setProjectSkillEnabled(
  _projectId: string,
  skillId: string,
  enabled: boolean,
): Promise<ProjectSkillsResponse> {
  return fetchJson<ProjectSkillsResponse>(
    `/api/projects/current/skills/${encodeURIComponent(skillId)}`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ enabled }),
    },
  );
}

export function importSkillManifest(
  raw: unknown,
  prompt?: string,
): Promise<SkillCatalogResponse> {
  const manifest = normalizeSkillManifest(raw);
  return fetchJson<SkillCatalogResponse>("/api/skills/import", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ manifest, prompt }),
  });
}

export function deleteSkill(skillId: string): Promise<SkillCatalogResponse> {
  return fetchJson<SkillCatalogResponse>(`/api/skills/${encodeURIComponent(skillId)}`, {
    method: "DELETE",
  });
}
