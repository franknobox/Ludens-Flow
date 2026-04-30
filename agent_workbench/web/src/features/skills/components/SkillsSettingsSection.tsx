import { useEffect, useMemo, useRef, useState } from "react";

import {
  deleteSkill,
  getSkillsCatalog,
  importSkillManifest,
} from "../api";
import type { SkillAgentScope, SkillManifest } from "../types";

const AGENT_OPTIONS: Array<{ value: SkillAgentScope; label: string }> = [
  { value: "design", label: "Design" },
  { value: "pm", label: "PM" },
  { value: "engineering", label: "Engineering" },
  { value: "review", label: "Review" },
];

function sourceLabel(): string {
  return "外部";
}

function readFileText(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ""));
    reader.onerror = () => reject(new Error(`读取文件失败：${file.name}`));
    reader.readAsText(file, "utf-8");
  });
}

export function SkillsSettingsSection() {
  const [skills, setSkills] = useState<SkillManifest[]>([]);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState("");
  const skillJsonInputRef = useRef<HTMLInputElement>(null);
  const folderInputRef = useRef<HTMLInputElement>(null);

  const grouped = useMemo(
    () =>
      skills.reduce<Record<string, SkillManifest[]>>((acc, skill) => {
        const key = skill.source;
        if (!acc[key]) acc[key] = [];
        acc[key]!.push(skill);
        return acc;
      }, {}),
    [skills],
  );

  const refresh = async () => {
    setLoading(true);
    try {
      const response = await getSkillsCatalog();
      setSkills(response.skills);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    folderInputRef.current?.setAttribute("webkitdirectory", "");
    folderInputRef.current?.setAttribute("directory", "");
    void refresh();
  }, []);

  const importFromSkillJson = async (file: File, prompt?: string) => {
    const text = await readFileText(file);
    const parsed = JSON.parse(text) as unknown;
    const response = await importSkillManifest(parsed, prompt);
    setSkills(response.skills);
    setMessage(`已导入 ${file.name}`);
  };

  const handleSkillJsonInput = async (files: FileList | null) => {
    const file = files?.[0];
    if (!file) return;
    setMessage("");
    try {
      await importFromSkillJson(file);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      if (skillJsonInputRef.current) skillJsonInputRef.current.value = "";
    }
  };

  const handleFolderInput = async (files: FileList | null) => {
    if (!files?.length) return;
    setMessage("");
    try {
      const skillJson = Array.from(files).find((file) =>
        file.webkitRelativePath
          ? file.webkitRelativePath.endsWith("/skill.json")
          : file.name === "skill.json",
      );
      if (!skillJson) {
        throw new Error("所选文件夹中没有找到 skill.json。");
      }
      const skillDir = skillJson.webkitRelativePath.replace(/skill\.json$/, "");
      const promptFile = Array.from(files).find((file) =>
        file.webkitRelativePath
          ? file.webkitRelativePath === `${skillDir}prompt.md`
          : file.name === "prompt.md",
      );
      const prompt = promptFile ? await readFileText(promptFile) : undefined;
      await importFromSkillJson(skillJson, prompt);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      if (folderInputRef.current) folderInputRef.current.value = "";
    }
  };

  const handleDelete = async (skill: SkillManifest) => {
    if (!window.confirm(`确认删除 Skill「${skill.name}」吗？`)) return;
    const response = await deleteSkill(skill.id);
    setSkills(response.skills);
    setMessage(`已删除 ${skill.name}`);
  };

  return (
    <div className="settings-detail-stack settings-detail-stack--fill">
      <section className="settings-pane-card settings-skills-whole">
        <div className="settings-skills-layout">
          <div className="settings-skills-list-area">
            <div className="settings-card-head">
              <h2 className="settings-card-title">Skills 管理</h2>
              <span className="settings-chip">{skills.length} 项</span>
            </div>

            {loading ? (
              <div className="settings-empty">正在加载 Skills...</div>
            ) : !skills.length ? (
              <div className="settings-empty">当前工作台还没有安装 Skill。</div>
            ) : (
              <div className="settings-skill-groups">
                {Object.entries(grouped).map(([source, items]) => (
                  <section key={source} className="settings-skill-group">
                    <div className="tool-group-head">
                      <h3>{sourceLabel()}</h3>
                      <span className="settings-chip">{items.length} 项</span>
                    </div>
                    <div className="settings-skill-list">
                      {items.map((skill) => (
                        <article key={skill.id} className="settings-skill-card">
                          <div>
                            <div className="skill-card-title-row">
                              <h3>{skill.name}</h3>
                              <span className="settings-chip subtle">v{skill.version}</span>
                            </div>
                            <p>{skill.description}</p>
                            <div className="skill-card-meta">
                              {skill.agents.map((agent) => (
                                <span key={agent} className="settings-chip subtle">
                                  {agent}
                                </span>
                              ))}
                              {skill.tags.map((tag) => (
                                <span key={tag} className="settings-chip subtle">
                                  {tag}
                                </span>
                              ))}
                            </div>
                          </div>
                          <button
                            type="button"
                            className="settings-pill-button danger"
                            onClick={() => {
                              void handleDelete(skill);
                            }}
                          >
                            删除
                          </button>
                        </article>
                      ))}
                    </div>
                  </section>
                ))}
              </div>
            )}
          </div>

          <div className="settings-skills-import-area">
            <div className="settings-card-head compact">
              <h2 className="settings-card-title">导入 Skill</h2>
            </div>
            <div className="settings-form">
              <input
                ref={skillJsonInputRef}
                type="file"
                accept=".json,application/json"
                hidden
                onChange={(event) => {
                  void handleSkillJsonInput(event.target.files);
                }}
              />
              <input
                ref={folderInputRef}
                type="file"
                multiple
                hidden
                onChange={(event) => {
                  void handleFolderInput(event.target.files);
                }}
              />

              <div className="settings-skill-import-actions">
                <button
                  type="button"
                  className="settings-primary-button"
                  onClick={() => skillJsonInputRef.current?.click()}
                >
                  选择 skill.json
                </button>
                <button
                  type="button"
                  className="settings-pill-button"
                  onClick={() => folderInputRef.current?.click()}
                >
                  选择 Skill 文件夹
                </button>
              </div>

              <div className="settings-skill-format">
                <strong>推荐结构</strong>
                <code>
                  skills/example-skill/skill.json
                  {"\n"}skills/example-skill/prompt.md
                  {"\n"}skills/example-skill/examples/
                </code>
              </div>

              {message ? <div className="settings-skill-message">{message}</div> : null}

              <div className="settings-skill-format">
                <strong>skill.json 必填字段</strong>
                <code>
                  {JSON.stringify(
                    {
                      id: "unity-helper",
                      name: "Unity Helper",
                      description: "Skill description",
                      version: "0.1.0",
                      agents: AGENT_OPTIONS.map((item) => item.value),
                      tags: ["Unity"],
                    },
                    null,
                    2,
                  )}
                </code>
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
