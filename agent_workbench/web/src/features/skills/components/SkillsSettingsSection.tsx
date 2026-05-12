import { useEffect, useMemo, useRef, useState } from "react";

import {
  deleteSkill,
  getSkillsCatalog,
  importSkillGithub,
  importSkillManifest,
  importSkillPackageFiles,
  importSkillZip,
} from "../api";
import type { SkillPackageFile } from "../api";
import type { SkillAgentScope, SkillManifest } from "../types";

const AGENT_OPTIONS: Array<{ value: SkillAgentScope; label: string }> = [
  { value: "design", label: "Design" },
  { value: "pm", label: "PM" },
  { value: "engineering", label: "Engineering" },
  { value: "review", label: "Review" },
];

function sourceLabel(source: string): string {
  if (source === "self" || source === "draft") return "自我沉淀";
  return "外部";
}

function sourceClass(source: string): string {
  return source === "self" || source === "draft" ? " self" : "";
}

function displayTags(skill: SkillManifest): string[] {
  const tags = [...skill.tags];
  if ((skill.source === "self" || skill.source === "draft") && !tags.includes("自我沉淀")) {
    tags.unshift("自我沉淀");
  }
  return tags;
}

function readFileText(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ""));
    reader.onerror = () => reject(new Error(`读取文件失败：${file.name}`));
    reader.readAsText(file, "utf-8");
  });
}

function readFileDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ""));
    reader.onerror = () => reject(new Error(`读取文件失败：${file.name}`));
    reader.readAsDataURL(file);
  });
}

export function SkillsSettingsSection() {
  const [skills, setSkills] = useState<SkillManifest[]>([]);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState("");
  const [messageKind, setMessageKind] = useState<"success" | "error">("success");
  const [selectedSkillId, setSelectedSkillId] = useState("");
  const [githubUrl, setGithubUrl] = useState("");
  const [selfCaptureEnabled, setSelfCaptureEnabled] = useState(false);
  const skillJsonInputRef = useRef<HTMLInputElement>(null);
  const folderInputRef = useRef<HTMLInputElement>(null);
  const zipInputRef = useRef<HTMLInputElement>(null);

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
  const selectedSkill = useMemo(
    () => skills.find((skill) => skill.id === selectedSkillId) || skills[0],
    [selectedSkillId, skills],
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
    setMessageKind("success");
    setMessage(`已导入 ${file.name}`);
  };

  const handleSkillJsonInput = async (files: FileList | null) => {
    const file = files?.[0];
    if (!file) return;
    setMessage("");
    try {
      await importFromSkillJson(file);
    } catch (error) {
      setMessageKind("error");
      setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      if (skillJsonInputRef.current) skillJsonInputRef.current.value = "";
    }
  };

  const handleFolderInput = async (files: FileList | null) => {
    if (!files?.length) return;
    setMessage("");
    try {
      const fileList = Array.from(files);
      const manifestFile = fileList.find((file) =>
        file.webkitRelativePath
          ? file.webkitRelativePath.endsWith("/skill.json") ||
            file.webkitRelativePath.endsWith("/SKILL.md")
          : file.name === "skill.json" || file.name === "SKILL.md",
      );
      if (!manifestFile) {
        throw new Error("所选文件夹中没有找到 skill.json 或 SKILL.md。");
      }
      const packageFiles: SkillPackageFile[] = [];
      for (const file of fileList) {
        const path = file.webkitRelativePath || file.name;
        packageFiles.push({
          path,
          data_url: await readFileDataUrl(file),
        });
      }
      const response = await importSkillPackageFiles(packageFiles);
      setSkills(response.skills);
      setMessageKind("success");
      setMessage(`已导入 ${manifestFile.webkitRelativePath || manifestFile.name}`);
    } catch (error) {
      setMessageKind("error");
      setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      if (folderInputRef.current) folderInputRef.current.value = "";
    }
  };

  const handleZipInput = async (files: FileList | null) => {
    const file = files?.[0];
    if (!file) return;
    setMessage("");
    try {
      const response = await importSkillZip(await readFileDataUrl(file));
      setSkills(response.skills);
      setMessageKind("success");
      setMessage(`已导入 ${file.name}`);
    } catch (error) {
      setMessageKind("error");
      setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      if (zipInputRef.current) zipInputRef.current.value = "";
    }
  };

  const handleGithubImport = async () => {
    const url = githubUrl.trim();
    if (!url) return;
    setMessage("");
    try {
      const response = await importSkillGithub(url);
      setSkills(response.skills);
      setGithubUrl("");
      setMessageKind("success");
      setMessage("已从 GitHub 导入 Skill。");
    } catch (error) {
      setMessageKind("error");
      setMessage(error instanceof Error ? error.message : String(error));
    }
  };

  const handleDelete = async (skill: SkillManifest) => {
    if (!window.confirm(`确认删除 Skill「${skill.name}」吗？`)) return;
    const response = await deleteSkill(skill.id);
    setSkills(response.skills);
    setMessageKind("success");
    setMessage(`已删除 ${skill.name}`);
  };

  return (
    <div className="settings-detail-stack settings-detail-stack--fill">
      <section className="settings-pane-card settings-skills-whole">
        <div className="settings-card-head settings-skills-topline">
          <div>
            <h2 className="settings-card-title">Skills 管理</h2>
            <p className="settings-card-subtitle">
              管理外部导入和自我沉淀的 Skill，并在工作台中按项目启用。
            </p>
          </div>
          <span className="settings-chip">{skills.length} 项</span>
        </div>

        <div className="settings-skills-layout">
          <div className="settings-skills-list-area">
            <div className={`settings-skill-self-toggle${selfCaptureEnabled ? " is-on" : ""}`}>
              <div>
                <strong>自我沉淀</strong>
                <span>
                  开启后进入沉淀状态。
                </span>
              </div>
              <label className="settings-toggle">
                <input
                  type="checkbox"
                  checked={selfCaptureEnabled}
                  onChange={(event) => setSelfCaptureEnabled(event.target.checked)}
                />
                <span>{selfCaptureEnabled ? "已开启" : "未开启"}</span>
              </label>
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
                      <h3>{sourceLabel(source)}</h3>
                      <span className="settings-chip">{items.length} 项</span>
                    </div>
                    <div className="settings-skill-list">
                      {items.map((skill) => (
                        <article
                          key={skill.id}
                          className={`settings-skill-card ${
                            selectedSkill?.id === skill.id ? "is-active" : ""
                          }`}
                        >
                          <div
                            role="button"
                            tabIndex={0}
                            onClick={() => setSelectedSkillId(skill.id)}
                            onKeyDown={(event) => {
                              if (event.key === "Enter") setSelectedSkillId(skill.id);
                            }}
                          >
                            <div className="skill-card-title-row">
                              <h3>{skill.name}</h3>
                              <span className="settings-chip subtle">v{skill.version}</span>
                              <span className={`settings-chip source${sourceClass(skill.source)}`}>
                                {sourceLabel(skill.source)}
                              </span>
                            </div>
                            <p>{skill.description}</p>
                            <div className="skill-card-meta">
                              {skill.agents.map((agent) => (
                                <span key={agent} className="settings-chip subtle">
                                  {agent}
                                </span>
                              ))}
                              {displayTags(skill).map((tag) => (
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
              <input
                ref={zipInputRef}
                type="file"
                accept=".zip,application/zip"
                hidden
                onChange={(event) => {
                  void handleZipInput(event.target.files);
                }}
              />

              <div className="settings-skill-import-actions">
                <button
                  type="button"
                  className="settings-pill-button"
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
                <button
                  type="button"
                  className="settings-pill-button"
                  onClick={() => zipInputRef.current?.click()}
                >
                  选择 zip
                </button>
              </div>

              <div className="settings-inline-row">
                <input
                  value={githubUrl}
                  onChange={(event) => setGithubUrl(event.target.value)}
                  placeholder="GitHub 仓库 URL"
                />
                <button
                  type="button"
                  className="settings-pill-button"
                  onClick={() => {
                    void handleGithubImport();
                  }}
                >
                  导入
                </button>
              </div>

              {message ? (
                <div className={`settings-skill-message ${messageKind}`}>{message}</div>
              ) : null}

              {selectedSkill ? (
                <div className="settings-skill-format">
                  <strong>当前详情</strong>
                  <code>
                    {[
                      `id: ${selectedSkill.id}`,
                      `name: ${selectedSkill.name}`,
                      `source: ${sourceLabel(selectedSkill.source)}`,
                      `agents: ${selectedSkill.agents.join(", ")}`,
                      `tags: ${displayTags(selectedSkill).join(", ") || "-"}`,
                    ].join("\n")}
                  </code>
                </div>
              ) : null}

              <details className="settings-skill-details">
                <summary>导入格式说明</summary>
                <div className="settings-skill-details-body">
                  <strong>推荐结构</strong>
                  <code>
                    skills/example-skill/skill.json
                    {"\n"}skills/example-skill/prompt.md
                    {"\n"}skills/example-skill/assets/
                    {"\n"}skills/example-skill/examples/
                  </code>
                  <strong>skill.json 必填字段</strong>
                  <code>
                    {JSON.stringify(
                      {
                        id: "engine-helper",
                        name: "Engine Helper",
                        description: "Skill description",
                        version: "0.1.0",
                        agents: AGENT_OPTIONS.map((item) => item.value),
                        tags: ["Engine"],
                      },
                      null,
                      2,
                    )}
                  </code>
                </div>
              </details>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
