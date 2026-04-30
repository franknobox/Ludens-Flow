import { useEffect, useMemo, useState } from "react";

import { getProjectSkills, setProjectSkillEnabled } from "../api";
import type { SkillAgentScope, SkillManifest } from "../types";

const AGENT_FILTERS: Array<{ value: "all" | SkillAgentScope; label: string }> = [
  { value: "all", label: "全部" },
  { value: "design", label: "Design" },
  { value: "pm", label: "PM" },
  { value: "engineering", label: "Engineering" },
  { value: "review", label: "Review" },
];

interface SkillsWorkbenchPageProps {
  projectId: string;
}

export function SkillsWorkbenchPage({ projectId }: SkillsWorkbenchPageProps) {
  const [skills, setSkills] = useState<SkillManifest[]>([]);
  const [enabledSkillIds, setEnabledSkillIds] = useState<Set<string>>(new Set());
  const [agentFilter, setAgentFilter] = useState<"all" | SkillAgentScope>("all");
  const [loading, setLoading] = useState(true);

  const enabledCount = enabledSkillIds.size;
  const filteredSkills = useMemo(
    () =>
      agentFilter === "all"
        ? skills
        : skills.filter((skill) => skill.agents.includes(agentFilter)),
    [agentFilter, skills],
  );

  const refresh = async () => {
    setLoading(true);
    try {
      const response = await getProjectSkills(projectId);
      setSkills(response.skills);
      setEnabledSkillIds(new Set(response.enabled_skill_ids));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void refresh();
  }, [projectId]);

  const toggleSkill = async (skillId: string, enabled: boolean) => {
    setEnabledSkillIds((prev) => {
      const next = new Set(prev);
      if (enabled) next.add(skillId);
      else next.delete(skillId);
      return next;
    });
    const response = await setProjectSkillEnabled(projectId, skillId, enabled);
    setSkills(response.skills);
    setEnabledSkillIds(new Set(response.enabled_skill_ids));
  };

  return (
    <div className="skills-page">
      <section className="skills-panel">
        <div className="skills-page-head">
          <div>
            <div className="skills-kicker">PROJECT SKILLS</div>
            <h1>当前项目 Skills</h1>
          </div>
          <div className="skills-summary">
            <span>可用 {skills.length}</span>
            <span>已启用 {enabledCount}</span>
          </div>
        </div>

        <div className="skills-panel-head">
          <div className="skills-filter-row">
            {AGENT_FILTERS.map((item) => (
              <button
                key={item.value}
                type="button"
                className={`skills-filter-chip${agentFilter === item.value ? " is-active" : ""}`}
                onClick={() => setAgentFilter(item.value)}
              >
                {item.label}
              </button>
            ))}
          </div>
          <span className="skills-count">{filteredSkills.length} 项</span>
        </div>

        {loading ? (
          <div className="skills-empty">正在加载 Skills...</div>
        ) : !filteredSkills.length ? (
          <div className="skills-empty">当前筛选下没有可用 Skill。</div>
        ) : (
          <div className="skills-list">
            {filteredSkills.map((skill) => {
              const enabled = enabledSkillIds.has(skill.id);
              return (
                <article key={skill.id} className={`skill-card${enabled ? " is-enabled" : ""}`}>
                  <div className="skill-card-main">
                    <div className="skill-card-title-row">
                      <h3>{skill.name}</h3>
                      <span className="skills-pill">外部</span>
                    </div>
                    <p>{skill.description}</p>
                  </div>
                  <div className="skill-card-meta">
                    {skill.agents.map((agent) => (
                      <span key={agent} className="skills-pill subtle">
                        {agent}
                      </span>
                    ))}
                    {skill.tags.slice(0, 4).map((tag) => (
                      <span key={tag} className="skills-pill subtle">
                        {tag}
                      </span>
                    ))}
                  </div>
                  <label className="skill-switch">
                    <input
                      type="checkbox"
                      checked={enabled}
                      onChange={(event) => {
                        void toggleSkill(skill.id, event.target.checked);
                      }}
                    />
                    <span>{enabled ? "已启用" : "未启用"}</span>
                  </label>
                </article>
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
}
