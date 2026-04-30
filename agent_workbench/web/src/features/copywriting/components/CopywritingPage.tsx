import { useMemo, useState } from "react";

import { generateDesignCopywriting } from "../api/copywriting";
import type { DesignCopywritingCandidate, DesignCopywritingResponse } from "../types";
import { toErrorMessage } from "../../workbench/utils";
import "../styles/copywriting.css";

type CopyType = {
  id: string;
  name: string;
  desc: string;
  examples: string[];
};

const COPY_TYPES: CopyType[] = [
  {
    id: "dialogue",
    name: "角色台词",
    desc: "用于 NPC 对话、剧情对白、战斗喊话和事件反应。",
    examples: ["首次见面", "任务推进", "战斗触发"],
  },
  {
    id: "item",
    name: "物品描述",
    desc: "用于背包、商店、掉落、装备和收藏品说明。",
    examples: ["短描述", "风味文本", "稀有度差异"],
  },
  {
    id: "world",
    name: "世界观片段",
    desc: "用于地区介绍、阵营背景、历史传说和规则说明。",
    examples: ["地区传闻", "阵营档案", "古老事件"],
  },
  {
    id: "naming",
    name: "命名生成",
    desc: "用于角色名、地名、技能名、道具名和组织名。",
    examples: ["中文名", "英文名", "系列命名"],
  },
  {
    id: "quest",
    name: "任务文本",
    desc: "用于任务标题、目标说明、阶段提示和完成反馈。",
    examples: ["任务标题", "目标文案", "完成提示"],
  },
];

const STYLE_PRESETS = ["简洁直接", "细腻叙事", "口语自然", "诗性凝练"];
const LENGTH_PRESETS = ["极短", "短句", "标准", "较长"];
const PROJECT_REFERENCE_IDS = ["gdd", "project_plan"];
const FUTURE_REFERENCE_ITEMS = [
  { id: "characters", name: "角色资料", desc: "角色身份、关系、口癖和语气边界" },
  { id: "world_terms", name: "世界观与术语", desc: "地区、阵营、道具、技能和统一命名" },
  { id: "style_rules", name: "文案规则", desc: "风格样本、禁用词、长度和用途限制" },
  { id: "external_files", name: "外部资料", desc: "后续支持上传参考文件、设定表和样本文案" },
];

function splitList(value: string): string[] {
  return value
    .replace(/，/g, ",")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function safeFileName(value: string): string {
  return value.trim().replace(/[\\/:*?"<>|]+/g, "-").replace(/\s+/g, "-") || "copywriting";
}

function csvCell(value: string): string {
  return `"${value.replace(/"/g, '""')}"`;
}

function downloadTextFile(filename: string, content: string, mimeType: string) {
  const blob = new Blob([content], { type: `${mimeType};charset=utf-8` });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

function buildMarkdownExport(response: DesignCopywritingResponse, copyTypeName: string): string {
  const request = response.request;
  const lines = [
    `# ${copyTypeName} 文案候选`,
    "",
    `- 类型：${copyTypeName}`,
    `- 用途：${request.purpose || "-"}`,
    `- 风格：${request.style}`,
    `- 长度：${request.length}`,
    `- 数量：${response.candidates.length}`,
    "",
    "## 具体需求",
    "",
    request.brief || "-",
    "",
    "## 候选结果",
    "",
  ];

  response.candidates.forEach((candidate, index) => {
    lines.push(`### 候选 ${index + 1}`, "");
    lines.push(candidate.text, "");
    if (candidate.tags.length) {
      lines.push(`标签：${candidate.tags.join(" / ")}`, "");
    }
    if (candidate.notes.length) {
      lines.push(`备注：${candidate.notes.join(" / ")}`, "");
    }
  });

  return lines.join("\n");
}

function buildCsvExport(response: DesignCopywritingResponse, copyTypeName: string): string {
  const rows = [
    ["index", "type", "purpose", "style", "length", "text", "tags", "notes"],
    ...response.candidates.map((candidate, index) => [
      String(index + 1),
      copyTypeName,
      response.request.purpose || "",
      response.request.style,
      response.request.length,
      candidate.text,
      candidate.tags.join(" / "),
      candidate.notes.join(" / "),
    ]),
  ];
  return rows.map((row) => row.map(csvCell).join(",")).join("\n");
}

export function CopywritingPage() {
  const [activeTypeId, setActiveTypeId] = useState(COPY_TYPES[0].id);
  const [selectedStyle, setSelectedStyle] = useState(STYLE_PRESETS[0]);
  const [selectedLength, setSelectedLength] = useState(LENGTH_PRESETS[2]);
  const [quantity, setQuantity] = useState(5);
  const [brief, setBrief] = useState("");
  const [purpose, setPurpose] = useState("");
  const [mustInclude, setMustInclude] = useState("");
  const [mustAvoid, setMustAvoid] = useState("");
  const [includeProjectArtifacts, setIncludeProjectArtifacts] = useState(true);
  const [response, setResponse] = useState<DesignCopywritingResponse | null>(null);
  const [errorText, setErrorText] = useState("");
  const [statusText, setStatusText] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const activeType = useMemo(
    () => COPY_TYPES.find((item) => item.id === activeTypeId) || COPY_TYPES[0],
    [activeTypeId],
  );

  const canGenerate = brief.trim().length > 0 && !submitting;
  const contextItems = response?.context?.artifacts || [];

  const handleGenerate = async () => {
    if (!brief.trim()) {
      setErrorText("请先填写具体需求。");
      return;
    }
    setSubmitting(true);
    setErrorText("");
    setStatusText("");
    try {
      const result = await generateDesignCopywriting({
        copy_type: activeTypeId,
        brief,
        purpose,
        quantity,
        style: selectedStyle,
        length: selectedLength,
        must_include: splitList(mustInclude),
        must_avoid: splitList(mustAvoid),
        reference_ids: includeProjectArtifacts ? PROJECT_REFERENCE_IDS : ["__none__"],
        language: "zh-CN",
      });
      setResponse(result);
      setStatusText(`已生成 ${result.candidates.length} 条候选`);
    } catch (error) {
      setErrorText(toErrorMessage(error));
    } finally {
      setSubmitting(false);
    }
  };

  const copyCandidate = async (candidate: DesignCopywritingCandidate) => {
    try {
      await navigator.clipboard.writeText(candidate.text);
      setStatusText("已复制单条文案");
      setErrorText("");
    } catch (error) {
      setErrorText(`复制失败：${toErrorMessage(error)}`);
    }
  };

  const exportMarkdown = () => {
    if (!response) return;
    downloadTextFile(
      `${safeFileName(activeType.name)}-copywriting.md`,
      buildMarkdownExport(response, activeType.name),
      "text/markdown",
    );
    setStatusText("已导出 Markdown");
  };

  const exportCsv = () => {
    if (!response) return;
    downloadTextFile(
      `${safeFileName(activeType.name)}-copywriting.csv`,
      buildCsvExport(response, activeType.name),
      "text/csv",
    );
    setStatusText("已导出 CSV");
  };

  return (
    <div className="copywriting-page" aria-label="文案加工台">
      <aside className="copywriting-rail">
        <div className="copywriting-rail-head">
          <span className="copywriting-kicker">策划子能力</span>
          <strong>文案类型</strong>
        </div>
        <div className="copywriting-type-list">
          {COPY_TYPES.map((type) => (
            <button
              key={type.id}
              type="button"
              className={`copywriting-type-card${type.id === activeTypeId ? " is-active" : ""}`}
              onClick={() => setActiveTypeId(type.id)}
            >
              <span>{type.name}</span>
              <small>{type.desc}</small>
            </button>
          ))}
        </div>
      </aside>

      <main className="copywriting-workbench">
        <section className="copywriting-panel copywriting-brief-panel">
          <header className="copywriting-hero copywriting-hero-compact">
            <div>
              <span className="copywriting-kicker">Copy Workshop</span>
              <h2>{activeType.name}</h2>
            </div>
          </header>

          <div className="copywriting-section-head">
            <h3>加工要求</h3>
            <button
              type="button"
              className={`copywriting-ghost-btn${includeProjectArtifacts ? " is-active" : ""}`}
              onClick={() => setIncludeProjectArtifacts((value) => !value)}
            >
              {includeProjectArtifacts ? "已载入项目工件" : "不载入项目工件"}
            </button>
          </div>

          <div className="copywriting-form-grid">
            <label className="copywriting-field copywriting-field-wide">
              <span>具体需求</span>
              <textarea
                value={brief}
                onChange={(event) => setBrief(event.target.value)}
                placeholder="例如：为一名看似散漫但很可靠的武器店老板生成 5 句首次见面台词，语气轻松但不要太现代。"
              />
            </label>

            <label className="copywriting-field">
              <span>用途</span>
              <input
                type="text"
                value={purpose}
                onChange={(event) => setPurpose(event.target.value)}
                placeholder="例如：NPC 首次见面 / 商店介绍 / 任务完成"
              />
            </label>

            <label className="copywriting-field">
              <span>生成数量</span>
              <input
                type="number"
                min={1}
                max={30}
                value={quantity}
                onChange={(event) => {
                  const nextValue = Number(event.target.value);
                  setQuantity(Number.isFinite(nextValue) ? Math.min(30, Math.max(1, nextValue)) : 1);
                }}
              />
            </label>
          </div>

          <div className="copywriting-choice-row">
            <div>
              <span className="copywriting-choice-label">风格预设</span>
              <div className="copywriting-chip-row">
                {STYLE_PRESETS.map((style) => (
                  <button
                    key={style}
                    type="button"
                    className={`copywriting-chip${style === selectedStyle ? " is-active" : ""}`}
                    onClick={() => setSelectedStyle(style)}
                  >
                    {style}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <span className="copywriting-choice-label">长度</span>
              <div className="copywriting-chip-row">
                {LENGTH_PRESETS.map((length) => (
                  <button
                    key={length}
                    type="button"
                    className={`copywriting-chip${length === selectedLength ? " is-active" : ""}`}
                    onClick={() => setSelectedLength(length)}
                  >
                    {length}
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div className="copywriting-constraint-grid">
            <label className="copywriting-field">
              <span>必须包含</span>
              <input
                type="text"
                value={mustInclude}
                onChange={(event) => setMustInclude(event.target.value)}
                placeholder="关键词、角色名、道具名"
              />
            </label>
            <label className="copywriting-field">
              <span>必须避免</span>
              <input
                type="text"
                value={mustAvoid}
                onChange={(event) => setMustAvoid(event.target.value)}
                placeholder="禁词、出戏表达、设定冲突"
              />
            </label>
          </div>

          <div className="copywriting-actions">
            <div className="copywriting-action-note">
              {errorText || statusText || (response ? `已生成 ${response.candidates.length} 条候选` : "将通过策划 Agent 生成结构化候选。")}
            </div>
            <button
              type="button"
              className="copywriting-primary-btn"
              disabled={!canGenerate}
              onClick={() => {
                void handleGenerate();
              }}
            >
              {submitting ? "生成中..." : "生成文案"}
            </button>
          </div>
        </section>

        <section className="copywriting-panel copywriting-result-panel">
          <div className="copywriting-section-head">
            <div>
              <span className="copywriting-kicker">Output</span>
              <h3>候选结果</h3>
            </div>
            <div className="copywriting-result-actions">
              <button type="button" disabled={!response?.candidates.length} onClick={exportMarkdown}>
                导出 MD
              </button>
              <button type="button" disabled={!response?.candidates.length} onClick={exportCsv}>
                导出 CSV
              </button>
            </div>
          </div>

          {response?.candidates.length ? (
            <div className="copywriting-result-list">
              {response.candidates.map((candidate, index) => (
                <article key={candidate.id || index} className="copywriting-result-card">
                  <div className="copywriting-result-card-head">
                    <strong>候选 {index + 1}</strong>
                    <div className="copywriting-result-card-tools">
                      {candidate.tags.length ? (
                        <div className="copywriting-result-tags">
                          {candidate.tags.slice(0, 4).map((tag) => (
                            <span key={tag}>{tag}</span>
                          ))}
                        </div>
                      ) : null}
                      <button
                        type="button"
                        className="copywriting-copy-btn"
                        onClick={() => {
                          void copyCandidate(candidate);
                        }}
                      >
                        复制
                      </button>
                    </div>
                  </div>
                  <p>{candidate.text}</p>
                  {candidate.notes.length ? (
                    <small>{candidate.notes.join(" / ")}</small>
                  ) : null}
                </article>
              ))}
            </div>
          ) : (
            <div className="copywriting-empty-result">
              <strong>{submitting ? "正在生成" : "等待生成"}</strong>
              <span>这里会展示策划 Agent 返回的多条候选文案。</span>
            </div>
          )}
        </section>
      </main>

      <aside className="copywriting-codex">
        <div className="copywriting-codex-head">
          <span className="copywriting-kicker">Reference</span>
          <strong>参考资料</strong>
          <p>生成时优先参考项目资料，避免文案脱离当前游戏。</p>
        </div>

        <div className="copywriting-codex-list">
          {(contextItems.length ? contextItems : PROJECT_REFERENCE_IDS.map((id) => ({
            id,
            name: id === "gdd" ? "GDD.md" : "PROJECT_PLAN.md",
            source: "artifact",
            content: "",
          }))).map((item) => (
            <div
              key={item.id}
              className={`copywriting-codex-item${includeProjectArtifacts ? " is-active" : ""}`}
            >
              <div>
                <strong>{item.name}</strong>
                <span>{item.source === "artifact" ? "项目工件" : item.source}</span>
              </div>
              <small>{includeProjectArtifacts ? "已启用" : "未启用"}</small>
            </div>
          ))}
          {FUTURE_REFERENCE_ITEMS.map((item) => (
            <div key={item.id} className="copywriting-codex-item">
              <div>
                <strong>{item.name}</strong>
                <span>{item.desc}</span>
              </div>
              <small>待接入</small>
            </div>
          ))}
        </div>
      </aside>
    </div>
  );
}
