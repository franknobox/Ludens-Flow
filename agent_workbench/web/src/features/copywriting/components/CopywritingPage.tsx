import { useEffect, useMemo, useRef, useState } from "react";
import type { ChangeEvent } from "react";

import { startDesignCopywritingJob } from "../api/copywriting";
import type { DesignCopywritingCandidate, DesignCopywritingResponse } from "../types";
import { useProjectRuntime } from "../../workbench/state/ProjectRuntimeContext";
import { toErrorMessage } from "../../workbench/utils";
import "../styles/copywriting.css";

type CopyType = {
  id: string;
  name: string;
  desc: string;
  examples: string[];
};

type ExternalReferenceFile = {
  id: string;
  name: string;
  mimeType: string;
  size: number;
  dataUrl: string;
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
const PROJECT_REFERENCE_IDS = ["gdd"];
const MAX_EXTERNAL_REFERENCES = 6;
const MAX_EXTERNAL_REFERENCE_BYTES = 5 * 1024 * 1024;
const EXTERNAL_REFERENCE_ACCEPT =
  ".txt,.md,.json,.yaml,.yml,.csv,.cs,.js,.ts,.tsx,.py,.shader,.hlsl,.uxml,.uss,.asmdef,.meta,application/pdf,.pdf";
const EXTERNAL_REFERENCE_EXTENSIONS = new Set([
  ".txt",
  ".md",
  ".json",
  ".yaml",
  ".yml",
  ".csv",
  ".cs",
  ".js",
  ".ts",
  ".tsx",
  ".py",
  ".shader",
  ".hlsl",
  ".uxml",
  ".uss",
  ".asmdef",
  ".meta",
  ".pdf",
]);
const FUTURE_REFERENCE_ITEMS = [
  { id: "characters", name: "角色资料", desc: "角色身份、关系、口癖和语气边界" },
  { id: "world_terms", name: "世界观与术语", desc: "地区、阵营、道具、技能和统一命名" },
  { id: "style_rules", name: "文案规则", desc: "风格样本、禁用词、长度和用途限制" },
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

function readFileAsDataUrl(file: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ""));
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

function isSupportedExternalReference(file: File): boolean {
  const lowerName = file.name.toLowerCase();
  return Array.from(EXTERNAL_REFERENCE_EXTENSIONS).some((ext) => lowerName.endsWith(ext));
}

function referenceFileMeta(file: ExternalReferenceFile): string {
  const sizeKb = Math.max(1, Math.round(file.size / 1024));
  return `${sizeKb} KB`;
}

async function collectExternalReferences(
  files: File[],
): Promise<{ references: ExternalReferenceFile[]; warnings: string[] }> {
  const references: ExternalReferenceFile[] = [];
  const warnings: string[] = [];

  for (const file of files.slice(0, MAX_EXTERNAL_REFERENCES)) {
    if (!isSupportedExternalReference(file)) {
      warnings.push(`${file.name}：不支持的文件类型。`);
      continue;
    }
    if (file.size > MAX_EXTERNAL_REFERENCE_BYTES) {
      warnings.push(`${file.name}：文件超过 5 MB。`);
      continue;
    }
    try {
      references.push({
        id: `${file.name}-${file.size}-${file.lastModified}-${Math.random().toString(36).slice(2, 8)}`,
        name: file.name,
        mimeType: file.type || "application/octet-stream",
        size: file.size,
        dataUrl: await readFileAsDataUrl(file),
      });
    } catch {
      warnings.push(`${file.name}：读取文件失败。`);
    }
  }

  return { references, warnings };
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
  if (response.table?.columns.length && response.table.rows.length) {
    const rows = [
      response.table.columns,
      ...response.table.rows.map((row) =>
        response.table?.columns.map((column) => row[column] || "") || [],
      ),
    ];
    return rows.map((row) => row.map(csvCell).join(",")).join("\n");
  }

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

function isDesignCopywritingResponse(value: unknown): value is DesignCopywritingResponse {
  if (!value || typeof value !== "object") {
    return false;
  }
  const record = value as Record<string, unknown>;
  return Array.isArray(record.candidates) && Boolean(record.request);
}

export function CopywritingPage() {
  const { subscribeEvents } = useProjectRuntime();
  const [activeTypeId, setActiveTypeId] = useState(COPY_TYPES[0].id);
  const [selectedStyle, setSelectedStyle] = useState(STYLE_PRESETS[0]);
  const [selectedLength, setSelectedLength] = useState(LENGTH_PRESETS[2]);
  const [quantity, setQuantity] = useState(5);
  const [brief, setBrief] = useState("");
  const [purpose, setPurpose] = useState("");
  const [mustInclude, setMustInclude] = useState("");
  const [mustAvoid, setMustAvoid] = useState("");
  const [mustIncludeExpanded, setMustIncludeExpanded] = useState(false);
  const [mustAvoidExpanded, setMustAvoidExpanded] = useState(false);
  const [includeProjectArtifacts, setIncludeProjectArtifacts] = useState(true);
  const [externalReferences, setExternalReferences] = useState<ExternalReferenceFile[]>([]);
  const [response, setResponse] = useState<DesignCopywritingResponse | null>(null);
  const [errorText, setErrorText] = useState("");
  const [statusText, setStatusText] = useState("");
  const [progressText, setProgressText] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [activeJobId, setActiveJobId] = useState("");
  const externalReferenceInputRef = useRef<HTMLInputElement>(null);

  const activeType = useMemo(
    () => COPY_TYPES.find((item) => item.id === activeTypeId) || COPY_TYPES[0],
    [activeTypeId],
  );

  const canGenerate = brief.trim().length > 0 && !submitting;
  const contextItems = response?.context?.artifacts || [];

  useEffect(
    () =>
      subscribeEvents((event) => {
        if (!activeJobId || event.job_id !== activeJobId) {
          return;
        }
        if (
          event.type === "copywriting_job_queued" ||
          event.type === "copywriting_job_progress"
        ) {
          setProgressText(event.message || "文案生成任务正在执行。");
          return;
        }
        if (event.type === "copywriting_job_completed") {
          if (isDesignCopywritingResponse(event.response)) {
            const result = event.response;
            setResponse(result);
            const tableRows = result.table?.rows.length || 0;
            setStatusText(
              tableRows
                ? `已生成 ${result.candidates.length} 条候选，Dialogue CSV ${tableRows} 行`
                : `已生成 ${result.candidates.length} 条候选`,
            );
          } else {
            setErrorText("文案生成完成，但返回结果格式异常。");
          }
          setProgressText("");
          setActiveJobId("");
          setSubmitting(false);
          return;
        }
        if (event.type === "copywriting_job_failed") {
          setErrorText(event.error || "文案生成失败。");
          setProgressText("");
          setActiveJobId("");
          setSubmitting(false);
        }
      }),
    [activeJobId, subscribeEvents],
  );

  const handleExternalReferenceChange = async (event: ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(event.target.files || []);
    event.target.value = "";
    if (!files.length) {
      return;
    }

    const availableSlots = Math.max(0, MAX_EXTERNAL_REFERENCES - externalReferences.length);
    if (!availableSlots) {
      setErrorText(`一次最多只能添加 ${MAX_EXTERNAL_REFERENCES} 个外部资料。`);
      return;
    }

    const { references, warnings } = await collectExternalReferences(files.slice(0, availableSlots));
    setExternalReferences((prev) =>
      [...prev, ...references].slice(0, MAX_EXTERNAL_REFERENCES),
    );
    setErrorText(warnings.join("\n"));
    if (references.length) {
      setStatusText(`已添加 ${references.length} 个外部资料`);
    }
  };

  const handleGenerate = async () => {
    if (!brief.trim()) {
      setErrorText("请先填写具体需求。");
      return;
    }
    setSubmitting(true);
    setErrorText("");
    setStatusText("");
    setResponse(null);
    setActiveJobId("");
    setProgressText("正在提交文案生成任务...");
    try {
      const job = await startDesignCopywritingJob({
        copy_type: activeTypeId,
        brief,
        purpose,
        quantity,
        style: selectedStyle,
        length: selectedLength,
        must_include: splitList(mustInclude),
        must_avoid: splitList(mustAvoid),
        reference_ids: includeProjectArtifacts ? PROJECT_REFERENCE_IDS : ["__none__"],
        external_references: externalReferences.map((file) => ({
          kind: "file",
          name: file.name,
          mime_type: file.mimeType,
          size: file.size,
          data_url: file.dataUrl,
        })),
        language: "zh-CN",
      });
      setActiveJobId(job.job_id);
      setProgressText("文案生成任务已创建。");
    } catch (error) {
      setErrorText(toErrorMessage(error));
      setSubmitting(false);
      setProgressText("");
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
    setStatusText(response.table ? "已导出游戏表 CSV" : "已导出 CSV");
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
            <button
              type="button"
              className={`copywriting-ghost-btn${includeProjectArtifacts ? " is-active" : ""}`}
              onClick={() => setIncludeProjectArtifacts((value) => !value)}
            >
              {includeProjectArtifacts ? "已载入项目工件" : "不载入项目工件"}
            </button>
          </header>

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
            <div className="copywriting-field copywriting-collapsible-field">
              <button
                type="button"
                className="copywriting-field-toggle"
                onClick={() => setMustIncludeExpanded((value) => !value)}
                aria-expanded={mustIncludeExpanded}
              >
                <span>必须包含</span>
                <strong>{mustIncludeExpanded ? "-" : "+"}</strong>
              </button>
              {mustIncludeExpanded ? (
                <input
                  type="text"
                  value={mustInclude}
                  onChange={(event) => setMustInclude(event.target.value)}
                  placeholder="关键词、角色名、道具名"
                />
              ) : null}
            </div>
            <div className="copywriting-field copywriting-collapsible-field">
              <button
                type="button"
                className="copywriting-field-toggle"
                onClick={() => setMustAvoidExpanded((value) => !value)}
                aria-expanded={mustAvoidExpanded}
              >
                <span>必须避免</span>
                <strong>{mustAvoidExpanded ? "-" : "+"}</strong>
              </button>
              {mustAvoidExpanded ? (
                  <input
                    type="text"
                    value={mustAvoid}
                    onChange={(event) => setMustAvoid(event.target.value)}
                    placeholder="禁词、出戏表达、设定冲突"
                  />
              ) : null}
            </div>
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
                {response?.table ? "导出游戏 CSV" : "导出 CSV"}
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
              {response.table?.rows.length ? (
                <div className="copywriting-table-preview">
                  <strong>游戏表预览</strong>
                  <span>
                    {response.table.kind} · {response.table.rows.length} 行 ·{" "}
                    {response.table.columns.join(", ")}
                  </span>
                </div>
              ) : null}
            </div>
          ) : (
            <div className="copywriting-empty-result">
              <strong>{submitting ? "正在生成" : "等待生成"}</strong>
              <span>
                {submitting
                  ? progressText || "正在等待策划 Agent 返回候选文案。"
                  : "这里会展示策划 Agent 返回的多条候选文案。"}
              </span>
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
            name: "GDD.md",
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
          <div className="copywriting-codex-item copywriting-external-reference-card">
            <div className="copywriting-external-reference-main">
              <strong>外部资料</strong>
              <span>上传参考文件、设定表和样本文案</span>
              {externalReferences.length ? (
                <div className="copywriting-external-reference-list">
                  {externalReferences.map((file) => (
                    <div key={file.id} className="copywriting-external-reference-file">
                      <span className="copywriting-external-file-icon">文件</span>
                      <div>
                        <strong>{file.name}</strong>
                        <small>{referenceFileMeta(file)}</small>
                      </div>
                      <button
                        type="button"
                        aria-label={`删除 ${file.name}`}
                        onClick={() =>
                          setExternalReferences((prev) =>
                            prev.filter((item) => item.id !== file.id),
                          )
                        }
                      >
                        x
                      </button>
                    </div>
                  ))}
                </div>
              ) : null}
            </div>
            <button
              type="button"
              className="copywriting-add-reference-btn"
              aria-label="添加外部资料"
              title="添加本地文件"
              onClick={() => externalReferenceInputRef.current?.click()}
            >
              +
            </button>
            <input
              ref={externalReferenceInputRef}
              type="file"
              accept={EXTERNAL_REFERENCE_ACCEPT}
              multiple
              hidden
              onChange={(event) => {
                void handleExternalReferenceChange(event);
              }}
            />
          </div>
        </div>
      </aside>
    </div>
  );
}
