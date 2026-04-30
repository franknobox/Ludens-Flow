export type SkillAgentScope = "design" | "pm" | "engineering" | "review";

export type SkillSource = "external";

export interface SkillManifest {
  id: string;
  name: string;
  description: string;
  version: string;
  source: SkillSource;
  agents: SkillAgentScope[];
  tags: string[];
  updated_at?: string;
}

export interface ProjectSkillState {
  project_id: string;
  enabled_skill_ids: string[];
}

export interface SkillCatalogResponse {
  skills: SkillManifest[];
}

export interface ProjectSkillsResponse extends ProjectSkillState {
  skills: SkillManifest[];
}
