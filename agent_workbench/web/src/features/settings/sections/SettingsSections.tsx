import { useState } from "react";

import type {
  McpConnectionConfig,
  McpConnectionStatus,
  ModelProfileSummary,
  ProjectMeta,
  ProjectSettingsResponse,
  ProjectWorkspace,
  ToolCatalogItem,
  UserProfileResponse,
} from "../../workbench/types";

export const WORKSPACE_KIND_OPTIONS = [
  { value: "unity", label: "Unity" },
  { value: "generic", label: "Generic" },
  { value: "godot", label: "Godot" },
  { value: "blender", label: "Blender" },
];

const MCP_ENGINE_OPTIONS: Array<{ value: McpConnectionConfig["engine"]; label: string }> = [
  { value: "unity", label: "Unity" },
  { value: "godot", label: "Godot" },
  { value: "blender", label: "Blender" },
  { value: "unreal", label: "Unreal Engine" },
];

type ModelRoutingValidation = {
  parsed: Record<string, unknown> | null;
  normalized: string;
  error: string;
};

type RouteTarget =
  | { scope: "global" }
  | { scope: "agent"; agent: string }
  | { scope: "agent_capability"; agent: string; capability: string };

const AGENT_ROUTE_ROWS = [
  { key: "design", label: "策划 Agent", hint: "GDD、设定讨论、文案等设计相关能力" },
  { key: "pm", label: "项目 Agent", hint: "排期、范围、里程碑和计划收敛" },
  { key: "engineering", label: "工程 Agent", hint: "工程讨论、实现指导、文件与 MCP 能力" },
  { key: "review", label: "评审 Agent", hint: "Review Gate、质量检查和风险判断" },
];

const CAPABILITY_ROUTE_ROWS = [
  {
    agent: "design",
    capability: "copywriting",
    label: "文案能力",
    hint: "归属策划 Agent；单独填写后覆盖策划 Agent 默认模型",
  },
  {
    agent: "engineering",
    capability: "mcp",
    label: "MCP 能力",
    hint: "归属工程 Agent；单独填写后覆盖工程 Agent 默认模型",
  },
];

function parseRoutingDraft(draft: string): Record<string, unknown> {
  try {
    const parsed = JSON.parse(draft || "{}") as unknown;
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
      return parsed as Record<string, unknown>;
    }
  } catch {
    // Keep the form usable even when the advanced JSON editor is temporarily invalid.
  }
  return {};
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? { ...(value as Record<string, unknown>) }
    : {};
}

function cleanRouteEntry(entry: Record<string, unknown>): Record<string, unknown> {
  const cleaned: Record<string, unknown> = {};
  for (const key of ["profile", "provider", "model", "base_url", "api_key_env"]) {
    const value = String(entry[key] || "").trim();
    if (value) cleaned[key] = value;
  }
  if (entry.temperature !== undefined && entry.temperature !== "") {
    const temperature = Number(entry.temperature);
    if (Number.isFinite(temperature)) cleaned.temperature = temperature;
  }
  return cleaned;
}

function getRouteEntry(routing: Record<string, unknown>, target: RouteTarget): Record<string, unknown> {
  if (target.scope === "global") {
    return asRecord(routing.global);
  }
  if (target.scope === "agent") {
    return asRecord(asRecord(routing.agents)[target.agent]);
  }
  return asRecord(
    asRecord(asRecord(routing.agent_capabilities)[target.agent])[target.capability],
  );
}

function updateRouteEntry(
  routing: Record<string, unknown>,
  target: RouteTarget,
  nextEntry: Record<string, unknown>,
): Record<string, unknown> {
  const next = { ...routing };
  const cleaned = cleanRouteEntry(nextEntry);
  const hasValue = Object.keys(cleaned).length > 0;

  if (target.scope === "global") {
    if (hasValue) next.global = cleaned;
    else delete next.global;
    return pruneRouting(next);
  }

  if (target.scope === "agent") {
    const agents = asRecord(next.agents);
    if (hasValue) agents[target.agent] = cleaned;
    else delete agents[target.agent];
    if (Object.keys(agents).length) next.agents = agents;
    else delete next.agents;
    return pruneRouting(next);
  }

  const agentCapabilities = asRecord(next.agent_capabilities);
  const capabilityMap = asRecord(agentCapabilities[target.agent]);
  if (hasValue) capabilityMap[target.capability] = cleaned;
  else delete capabilityMap[target.capability];

  if (Object.keys(capabilityMap).length) agentCapabilities[target.agent] = capabilityMap;
  else delete agentCapabilities[target.agent];

  if (Object.keys(agentCapabilities).length) next.agent_capabilities = agentCapabilities;
  else delete next.agent_capabilities;
  return pruneRouting(next);
}

function pruneRouting(routing: Record<string, unknown>): Record<string, unknown> {
  const next = { ...routing };
  for (const key of ["global", "agents", "capabilities", "agent_capabilities"]) {
    const value = next[key];
    if (value && typeof value === "object" && !Array.isArray(value) && !Object.keys(value).length) {
      delete next[key];
    }
  }
  return next;
}

function routeValue(routing: Record<string, unknown>, target: RouteTarget, field: string): string {
  const value = getRouteEntry(routing, target)[field];
  return value === undefined || value === null ? "" : String(value);
}

function ModelRouteRow(props: {
  title: string;
  hint: string;
  routing: Record<string, unknown>;
  target: RouteTarget;
  modelProfiles: ModelProfileSummary[];
  disabled: boolean;
  onChange: (target: RouteTarget, field: string, value: string) => void;
}) {
  const { title, hint, routing, target, modelProfiles, disabled, onChange } = props;
  const currentProfile = routeValue(routing, target, "profile");
  const profileExists = modelProfiles.some((profile) => profile.id === currentProfile);
  return (
    <div className="model-route-row">
      <div className="model-route-meta">
        <strong>{title}</strong>
        <span>{hint}</span>
      </div>
      <select
        className="model-route-control"
        value={currentProfile}
        onChange={(event) => onChange(target, "profile", event.target.value)}
        disabled={disabled}
      >
        <option value="">使用默认</option>
        {currentProfile && !profileExists ? (
          <option value={currentProfile}>{currentProfile}</option>
        ) : null}
        {modelProfiles.map((profile) => (
          <option key={profile.id} value={profile.id}>
            {profile.id}
            {profile.provider ? ` · ${profile.provider}` : ""}
          </option>
        ))}
      </select>
      <input
        className="model-route-control"
        value={routeValue(routing, target, "model")}
        onChange={(event) => onChange(target, "model", event.target.value)}
        disabled={disabled}
        placeholder="模型"
      />
      <input
        className="model-route-control"
        value={routeValue(routing, target, "temperature")}
        onChange={(event) => onChange(target, "temperature", event.target.value)}
        disabled={disabled}
        placeholder="Temp"
      />
    </div>
  );
}

function kindLabel(kind: string): string {
  if (kind === "unity") return "Unity";
  if (kind === "godot") return "Godot";
  if (kind === "blender") return "Blender";
  return "Generic";
}

function sourceLabel(source?: string): string {
  if (source === "legacy" || source === "legacy-api") return "兼容迁移";
  return "用户添加";
}

function toolCategoryLabel(category: string): string {
  if (category === "workspace") return "工作区";
  if (category === "unity") return "Unity";
  if (category === "research") return "检索";
  return "通用";
}

function toolStatusLabel(tool: ToolCatalogItem): string {
  if (tool.writes_files) return "可写入";
  if (tool.requires_workspace) return "需工作区";
  return "只读";
}

interface GeneralSettingsSectionProps {
  projectSettings: ProjectSettingsResponse | null;
  loading: boolean;
  settingsSubmitting: boolean;
  modelProfiles: ModelProfileSummary[];
  theme: string;
  modelRoutingDraft: string;
  modelRoutingDirty: boolean;
  modelRoutingValidation: ModelRoutingValidation;
  onToggleFileWrite: (enabled: boolean) => void;
  onToggleFileWriteConfirm: (required: boolean) => void;
  onThemeChange: (theme: string) => void;
  onModelRoutingDraftChange: (value: string) => void;
  onClearModelRouting: () => void;
  onSaveModelRouting: () => void;
}

interface UserProfileSectionProps {
  profile: UserProfileResponse | null;
  draft: string;
  dirty: boolean;
  loading: boolean;
  submitting: boolean;
  onDraftChange: (value: string) => void;
  onReload: () => void;
  onSave: () => void;
}

export function GeneralSettingsSection(props: GeneralSettingsSectionProps) {
  const {
    projectSettings,
    loading,
    settingsSubmitting,
    modelProfiles,
    theme,
    modelRoutingDraft,
    modelRoutingDirty,
    modelRoutingValidation,
    onToggleFileWrite,
    onToggleFileWriteConfirm,
    onThemeChange,
    onModelRoutingDraftChange,
    onClearModelRouting,
    onSaveModelRouting,
  } = props;
  const modelRoutingObject = parseRoutingDraft(modelRoutingDraft);
  const updateModelRoute = (target: RouteTarget, field: string, value: string) => {
    const currentEntry = getRouteEntry(modelRoutingObject, target);
    const nextEntry = {
      ...currentEntry,
      [field]: field === "temperature" ? value.trim() : value,
    };
    const nextRouting = updateRouteEntry(modelRoutingObject, target, nextEntry);
    onModelRoutingDraftChange(JSON.stringify(nextRouting, null, 2));
  };

  return (
    <div className="settings-detail-stack general-settings-stack">
      <section className="settings-pane-card settings-pane-card-main">
        <div className="settings-card-head">
          <h2 className="settings-card-title">通用设置</h2>
          <span className="settings-chip">
            {projectSettings?.agent_file_write_enabled ? "已开启" : "已关闭"}
          </span>
        </div>

        <div className="settings-form">
          <div className="settings-toggle-row">
          <label className="settings-toggle">
            <input
              type="checkbox"
              checked={projectSettings?.agent_file_write_enabled ?? true}
              disabled={loading || settingsSubmitting}
              onChange={(event) => onToggleFileWrite(event.target.checked)}
            />
            <span>允许 Agent 写入当前项目工作区中的文件</span>
          </label>

          <label className="settings-toggle">
            <input
              type="checkbox"
              checked={projectSettings?.agent_file_write_confirm_required ?? false}
              disabled={
                loading ||
                settingsSubmitting ||
                !(projectSettings?.agent_file_write_enabled ?? true)
              }
              onChange={(event) => onToggleFileWriteConfirm(event.target.checked)}
            />
            <span>
              每次写入前请求确认
              <small className="settings-toggle-hint">
                关闭后为安全自动执行模式：通过项目总开关、工作区可写、路径边界和文件类型白名单后，Agent 可直接写入。
              </small>
            </span>
          </label>

          </div>

          <div className="settings-note-strip">
            <span className="settings-note-item">
              关闭后，创建目录、写入、补丁、删除等写入类工具会被拒绝
            </span>
            <span className="settings-note-item">
              开启后，仍然会继续受工作区可写权限约束
            </span>
            <span className="settings-note-item">
              模式：{projectSettings?.agent_file_write_confirm_required ? "逐次确认" : "安全自动执行，无需逐次请求"}
            </span>
          </div>
        </div>

        <div className="settings-card-head" style={{ marginTop: 24 }}>
          <h2 className="settings-card-title">UI 主题</h2>
        </div>
        <div className="settings-form">
          <div className="theme-picker">
            {[
              {
                value: "light",
                label: "浅色圆角",
                desc: "明亮 · 柔和圆角",
                preview: (
                  <div className="theme-preview theme-preview-light">
                    <div className="tp-topbar" />
                    <div className="tp-body">
                      <div className="tp-sidebar" />
                      <div className="tp-main">
                        <div className="tp-card" />
                        <div className="tp-card tp-card-sm" />
                      </div>
                    </div>
                  </div>
                ),
              },
              {
                value: "dark",
                label: "深色直角",
                desc: "暗色 · 硬朗直角",
                preview: (
                  <div className="theme-preview theme-preview-dark">
                    <div className="tp-topbar" />
                    <div className="tp-body">
                      <div className="tp-sidebar" />
                      <div className="tp-main">
                        <div className="tp-card" />
                        <div className="tp-card tp-card-sm" />
                      </div>
                    </div>
                  </div>
                ),
              },
              ].map(({ value, label, desc, preview }) => (
              <button
                key={value}
                type="button"
                className={`theme-option${theme === value ? " is-active" : ""}`}
                onClick={() => onThemeChange(value)}
              >
                {preview}
                <div className="theme-option-meta">
                  <span className="theme-option-label">{label}</span>
                  <span className="theme-option-desc">{desc}</span>
                </div>
                {theme === value && (
                  <span className="theme-option-check">✓</span>
                )}
              </button>
            ))}
          </div>
        </div>
      </section>

      <section className="settings-pane-card settings-pane-card-main settings-model-routing-card">
        <div className="settings-card-head">
          <h2 className="settings-card-title">模型路由</h2>
          <span className="settings-chip">
            {modelRoutingDirty ? "有未保存修改" : "已同步"}
          </span>
        </div>

        <div className="settings-form settings-model-routing-form">
          <div className="settings-note-strip">
            <span className="settings-note-item">优先级：agent_capabilities</span>
            <span className="settings-note-item">
              {"> capabilities > agents > global"}
            </span>
            <span className="settings-note-item">最后回退到 .env 默认模型</span>
          </div>

          <div className="model-route-table">
            <div className="model-route-tgroup">
              <span>Agent 默认模型</span>
              <span>Profile</span>
              <span>Model</span>
              <span>Temp</span>
            </div>
            {AGENT_ROUTE_ROWS.map((agent) => (
              <ModelRouteRow
                key={agent.key}
                title={agent.label}
                hint={agent.hint}
                routing={modelRoutingObject}
                target={{ scope: "agent", agent: agent.key }}
                modelProfiles={modelProfiles}
                disabled={settingsSubmitting}
                onChange={updateModelRoute}
              />
            ))}
            <div className="model-route-tgroup">
              <span>专项能力覆盖</span>
              <span>Profile</span>
              <span>Model</span>
              <span>Temp</span>
            </div>
            {CAPABILITY_ROUTE_ROWS.map((capability) => (
              <ModelRouteRow
                key={`${capability.agent}:${capability.capability}`}
                title={capability.label}
                hint={capability.hint}
                routing={modelRoutingObject}
                target={{
                  scope: "agent_capability",
                  agent: capability.agent,
                  capability: capability.capability,
                }}
                modelProfiles={modelProfiles}
                disabled={settingsSubmitting}
                onChange={updateModelRoute}
              />
            ))}
          </div>

          {modelRoutingValidation.error ? (
            <div className="settings-inline-error">
              {modelRoutingValidation.error}
            </div>
          ) : null}

          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <button
              type="button"
              className="settings-primary-button"
              disabled={
                settingsSubmitting ||
                !modelRoutingDirty ||
                Boolean(modelRoutingValidation.error)
              }
              onClick={onSaveModelRouting}
            >
              保存模型路由
            </button>
            <button
              type="button"
              className="settings-pill-button"
              disabled={settingsSubmitting}
              onClick={onClearModelRouting}
              style={{ padding: "0 10px", height: 30, fontSize: 12, fontWeight: 600 }}
            >
              清空项目路由
            </button>
          </div>
        </div>
      </section>
    </div>
  );
}

export function UserProfileSection(props: UserProfileSectionProps) {
  const {
    profile,
    draft,
    dirty,
    loading,
    submitting,
    onDraftChange,
    onReload,
    onSave,
  } = props;

  return (
    <div className="settings-detail-stack settings-detail-stack--fill">
      <section className="settings-pane-card settings-pane-card-main settings-profile-card">
        <div className="settings-card-head">
          <div>
            <h2 className="settings-card-title">用户画像</h2>
            <p className="settings-card-subtitle">
              编辑当前项目的 USER_PROFILE.md。Agent 会在涉及身份、偏好、目标和约束时优先参考这里。
            </p>
          </div>
          <div className="settings-profile-actions">
            <button
              type="button"
              className="settings-pill-button"
              title="把当前项目磁盘上的 USER_PROFILE.md 再读一遍，覆盖前端编辑框里的内容。"
              disabled={loading || submitting}
              onClick={onReload}
            >
              刷新
            </button>
            <button
              type="button"
              className="settings-primary-button"
              disabled={loading || submitting || !dirty}
              onClick={onSave}
            >
              {submitting ? "保存中..." : "保存画像"}
            </button>
          </div>
        </div>

        <div className="settings-profile-path">
          {profile?.display_path || profile?.path || "当前项目尚未加载 USER_PROFILE.md"}
        </div>

        <label className="settings-field settings-profile-editor">
          <span>USER_PROFILE.md</span>
          <textarea
            value={draft}
            disabled={loading || submitting}
            onChange={(event) => onDraftChange(event.target.value)}
            placeholder="正在加载用户画像..."
          />
        </label>
      </section>
    </div>
  );
}

interface ToolsSectionProps {
  tools: ToolCatalogItem[];
  toolsByCategory: Record<string, ToolCatalogItem[]>;
}

export function ToolsSection({ tools, toolsByCategory }: ToolsSectionProps) {
  return (
    <div className="settings-detail-stack tools-detail-stack">
      <section className="settings-pane-card settings-pane-card-main settings-pane-scroll-frame">
        <div className="settings-card-head">
          <h2 className="settings-card-title">工具目录</h2>
          <span className="settings-chip">{tools.length} 项</span>
        </div>
        {!tools.length ? (
          <div className="settings-empty">当前还没有可展示的工具能力。</div>
        ) : (
          <div className="tools-group-list">
            {Object.entries(toolsByCategory).map(([category, items]) => (
              <section key={category} className="tool-group">
                <div className="tool-group-head">
                  <h3>{toolCategoryLabel(category)}</h3>
                  <span className="settings-chip">{items.length} 项</span>
                </div>
                <div className="tool-list">
                  {items.map((tool) => (
                    <article key={tool.name} className="tool-card">
                      <div className="tool-card-head">
                        <div>
                          <h4>{tool.name}</h4>
                          <div className="tool-card-meta">
                            <span className="settings-chip subtle">
                              {toolStatusLabel(tool)}
                            </span>
                            {tool.workspace_kind ? (
                              <span className="settings-chip subtle">
                                {kindLabel(tool.workspace_kind)}
                              </span>
                            ) : null}
                          </div>
                        </div>
                      </div>
                      <p className="tool-card-text">{tool.description}</p>
                    </article>
                  ))}
                </div>
              </section>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

function mcpStatusLabel(status?: McpConnectionStatus): string {
  if (!status) return "已配置";
  if (status.status === "not_configured") return "未配置";
  if (status.status === "configured") return "已配置";
  if (status.status === "reachable") return "可连接";
  if (status.status === "tools_loaded") return "工具列表已加载";
  return "连接失败";
}

function mcpStatusClass(status?: McpConnectionStatus): string {
  if (!status) return "neutral";
  if (status.status === "tools_loaded" || status.status === "reachable") return "ok";
  if (status.status === "failed") return "danger";
  if (status.status === "not_configured") return "muted";
  return "neutral";
}

interface EngineConnectionsSectionProps {
  loading: boolean;
  submitting: boolean;
  checking: boolean;
  connections: McpConnectionConfig[];
  statuses: Record<string, McpConnectionStatus>;
  engineInput: McpConnectionConfig["engine"];
  labelInput: string;
  commandInput: string;
  argsInput: string;
  envInput: string;
  onEngineChange: (value: McpConnectionConfig["engine"]) => void;
  onLabelChange: (value: string) => void;
  onCommandChange: (value: string) => void;
  onArgsChange: (value: string) => void;
  onEnvChange: (value: string) => void;
  onFillEnginePreset: (engine: McpConnectionConfig["engine"]) => void;
  onAddConnection: () => void;
  onUpdateConnection: (
    connectionId: string,
    patch: Partial<McpConnectionConfig>,
  ) => void;
  onRemoveConnection: (connectionId: string) => void;
  onCheckConnection: (connectionId: string) => void;
  onCheckAll: () => void;
}

type EngineGuideKey = Extract<McpConnectionConfig["engine"], "blender" | "unity" | "godot">;

function hasInstallGuide(engine: McpConnectionConfig["engine"]): engine is EngineGuideKey {
  return engine === "blender" || engine === "unity" || engine === "godot";
}

function EngineInstallGuideModal({
  engine,
  onClose,
  onFillPreset,
}: {
  engine: EngineGuideKey;
  onClose: () => void;
  onFillPreset: () => void;
}) {
  const engineName =
    engine === "unity" ? "Unity MCP" : engine === "godot" ? "Godot MCP" : "Blender MCP";

  return (
    <div
      className={`settings-guide-overlay settings-guide-overlay--${engine}`}
      role="dialog"
      aria-modal="true"
    >
      <div className="settings-guide-panel">
        <button
          type="button"
          className="settings-guide-close"
          aria-label={`关闭 ${engineName} 安装指引`}
          onClick={onClose}
        >
          ×
        </button>

        <div className="settings-guide-head">
          <span className="settings-guide-kicker">{engineName}</span>
          <h2>安装指引</h2>
          {engine === "unity" ? (
            <p>
              这一步会把 Unity Editor 和 Ludens-Flow 连接起来。先在 Unity 项目中安装
              MCP for Unity 包并启动编辑器侧服务，再在当前项目里保存 MCP 配置。
            </p>
          ) : null}
          {engine === "godot" ? (
            <p>
              这一步会把 Godot 和 Ludens-Flow 连接起来。Godot MCP 通过本机 Node.js
              命令启动，必要时用 GODOT_PATH 指向你的 Godot 可执行文件。
            </p>
          ) : null}
          {engine === "blender" ? (
            <p>
              这一步会把 Blender 和 Ludens-Flow 连接起来。先完成 Blender 插件安装，
              再在当前项目里保存 MCP 启动配置，最后回到这里做健康检查。
            </p>
          ) : null}
        </div>

        <div className="settings-guide-body">
          {engine === "unity" ? (
            <>
              <section className="settings-guide-step">
                <div className="settings-guide-step-index">1</div>
                <div>
                  <h3>确认本机环境</h3>
                  <p>需要先安装 Unity 2021.3 LTS+、Python 3.10+，并确保已经安装 uv。</p>
                  <p>如果还没有 uv，在 Windows PowerShell 里运行：</p>
                  <pre><code>powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"</code></pre>
                  <p>安装完成后重新打开终端，确认 uv 可用：</p>
                  <pre><code>uv --version</code></pre>
                </div>
              </section>

              <section className="settings-guide-step">
                <div className="settings-guide-step-index">2</div>
                <div>
                  <h3>在 Unity 项目中安装包</h3>
                  <ol>
                    <li>打开目标 Unity 项目。</li>
                    <li>进入 <code>Window / Package Manager</code>。</li>
                    <li>点击 <code>+</code>，选择 <code>Add package from git URL...</code>。</li>
                    <li>填入下面的 Git URL，然后等待 Unity 导入完成。</li>
                  </ol>
                  <pre><code>https://github.com/CoplayDev/unity-mcp.git?path=/MCPForUnity#main</code></pre>
                  <a
                    className="settings-guide-link"
                    href="https://github.com/CoplayDev/unity-mcp"
                    target="_blank"
                    rel="noreferrer"
                  >
                    打开 Unity MCP 仓库
                  </a>
                </div>
              </section>

              <section className="settings-guide-step">
                <div className="settings-guide-step-index">3</div>
                <div>
                  <h3>启动 Unity 编辑器侧服务</h3>
                  <ol>
                    <li>在 Unity 中打开 <code>窗口 / 面板 / MCP For Unity / Toggle MCP Window</code>（快捷键 <code>Ctrl+Shift+M</code>）。</li>
                    <li>在弹出的 MCP 面板中点击 <code>Start Server</code>，确认状态指示灯变绿（Session 建立）。</li>
                    <li>记下 HTTP 地址（默认 <code>http://127.0.0.1:8080</code>）。</li>
                  </ol>
                </div>
              </section>

              <section className="settings-guide-step">
                <div className="settings-guide-step-index">4</div>
                <div>
                  <h3>在 Ludens-Flow 中保存 MCP 配置</h3>
                  <p>推荐 HTTP 直连模式：启动命令填 HTTP 地址，启动参数和环境变量留空。</p>
                  <button
                    type="button"
                    className="settings-guide-inline-button"
                    onClick={onFillPreset}
                  >
                    一键填入添加表单
                  </button>
                  <div className="settings-guide-config-grid">
                    <div>
                      <span>启动命令</span>
                      <pre><code>http://127.0.0.1:8080</code></pre>
                    </div>
                    <div>
                      <span>启动参数，每行一个</span>
                      <pre><code>（留空）</code></pre>
                    </div>
                    <div>
                      <span>环境变量</span>
                      <pre><code>（留空）</code></pre>
                    </div>
                  </div>
                </div>
              </section>

              <section className="settings-guide-step">
                <div className="settings-guide-step-index">5</div>
                <div>
                  <h3>回到设置页检查连接</h3>
                  <p>
                    保存配置后点击“检查”。如果能读取工具列表，再去工作台的 Unity MCP
                    页面查看能力映射。
                  </p>
                </div>
              </section>
            </>
          ) : null}

          {engine === "godot" ? (
            <>
              <section className="settings-guide-step">
                <div className="settings-guide-step-index">1</div>
                <div>
                  <h3>确认本机环境</h3>
                  <p>需要先安装 Godot Engine，并确保本机已有 Node.js 18+ 和 npm。</p>
                  <p>在 Windows PowerShell 里可以先检查：</p>
                  <pre><code>node --version{"\n"}npm --version</code></pre>
                </div>
              </section>

              <section className="settings-guide-step">
                <div className="settings-guide-step-index">2</div>
                <div>
                  <h3>确认 Godot 可执行文件</h3>
                  <p>
                    如果 Godot 没有加入 PATH，建议准备好 <code>Godot.exe</code> 的完整路径，
                    后续填入 <code>GODOT_PATH</code> 环境变量。
                  </p>
                  <pre><code>{`GODOT_PATH=E:\\Tools\\Godot\\Godot_v4.4-stable_win64.exe`}</code></pre>
                  <a
                    className="settings-guide-link"
                    href="https://github.com/Coding-Solo/godot-mcp"
                    target="_blank"
                    rel="noreferrer"
                  >
                    打开 Godot MCP 仓库
                  </a>
                </div>
              </section>

              <section className="settings-guide-step">
                <div className="settings-guide-step-index">3</div>
                <div>
                  <h3>在 Ludens-Flow 中保存 MCP 配置</h3>
                  <p>
                    推荐使用 npx 启动。第一次检查时 npm 可能会下载依赖，等待时间会更长。
                    如果 Godot 已加入 PATH，环境变量可以留空；否则把等号后改成你的本机路径。
                  </p>
                  <button
                    type="button"
                    className="settings-guide-inline-button"
                    onClick={onFillPreset}
                  >
                    一键填入添加表单
                  </button>
                  <div className="settings-guide-config-grid">
                    <div>
                      <span>启动命令</span>
                      <pre><code>cmd</code></pre>
                    </div>
                    <div>
                      <span>启动参数，每行一个</span>
                      <pre><code>{"/c\nnpx\n-y\n@coding-solo/godot-mcp"}</code></pre>
                    </div>
                    <div>
                      <span>环境变量</span>
                      <pre><code>GODOT_PATH=</code></pre>
                    </div>
                  </div>
                </div>
              </section>

              <section className="settings-guide-step">
                <div className="settings-guide-step-index">4</div>
                <div>
                  <h3>回到设置页检查连接</h3>
                  <p>
                    保存配置后点击“检查”。如果能读取工具列表，再去工作台的 Godot MCP
                    页面查看能力映射。
                  </p>
                </div>
              </section>
            </>
          ) : null}

          {engine === "blender" ? (
            <>
              <section className="settings-guide-step">
                <div className="settings-guide-step-index">1</div>
                <div>
                  <h3>确认本机环境</h3>
                  <p>需要先安装 Blender 3.0+、Python 3.10+，并确保已经安装 uv。</p>
                  <p>如果还没有 uv，在 Windows PowerShell 里运行：</p>
                  <pre><code>powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"</code></pre>
                  <p>安装完成后重新打开终端，确认 uv 可用：</p>
                  <pre><code>uv --version</code></pre>
                </div>
              </section>

              <section className="settings-guide-step">
                <div className="settings-guide-step-index">2</div>
                <div>
                  <h3>下载 Blender 插件</h3>
                  <p>
                    打开 GitHub 文件页，将 <code>addon.py</code> 下载并保存到本地。
                    也可以用下面的 PowerShell 命令直接保存到下载目录。
                  </p>
                  <pre><code>{`Invoke-WebRequest -Uri "https://raw.githubusercontent.com/ahujasid/blender-mcp/main/addon.py" -OutFile "$env:USERPROFILE\\Downloads\\addon.py"`}</code></pre>
                  <a
                    className="settings-guide-link"
                    href="https://github.com/ahujasid/blender-mcp/blob/main/addon.py"
                    target="_blank"
                    rel="noreferrer"
                  >
                    打开 GitHub 文件页
                  </a>
                </div>
              </section>

              <section className="settings-guide-step">
                <div className="settings-guide-step-index">3</div>
                <div>
                  <h3>在 Blender 中启用插件</h3>
                  <ol>
                    <li>打开 Blender。</li>
                    <li>进入 Edit / Preferences / Add-ons。</li>
                    <li>点击 Install，选择刚下载的 <code>addon.py</code>。</li>
                    <li>启用 <code>Interface: Blender MCP</code>。</li>
                    <li>回到 3D View，按键盘 <code>N</code> 呼出右侧侧边栏。</li>
                    <li>在右侧侧边栏里找到 BlenderMCP 面板，点击连接按钮。</li>
                  </ol>
                </div>
              </section>

              <section className="settings-guide-step">
                <div className="settings-guide-step-index">4</div>
                <div>
                  <h3>在 Ludens-Flow 中保存 MCP 配置</h3>
                  <p>Windows 推荐使用下面这组配置，并默认关闭第三方 telemetry。</p>
                  <button
                    type="button"
                    className="settings-guide-inline-button"
                    onClick={onFillPreset}
                  >
                    一键填入添加表单
                  </button>
                  <div className="settings-guide-config-grid">
                    <div>
                      <span>启动命令</span>
                      <pre><code>cmd</code></pre>
                    </div>
                    <div>
                      <span>启动参数，每行一个</span>
                      <pre><code>{"/c\nuvx\nblender-mcp"}</code></pre>
                    </div>
                    <div>
                      <span>环境变量</span>
                      <pre><code>DISABLE_TELEMETRY=true</code></pre>
                    </div>
                  </div>
                </div>
              </section>

              <section className="settings-guide-step">
                <div className="settings-guide-step-index">5</div>
                <div>
                  <h3>回到设置页检查连接</h3>
                  <p>
                    保存配置后点击“检查”。如果能读取到底层工具列表，再去工作台的
                    Blender MCP 页面查看能力映射。
                  </p>
                </div>
              </section>
            </>
          ) : null}
        </div>

      </div>
    </div>
  );
}

export function EngineConnectionsSection(props: EngineConnectionsSectionProps) {
  const {
    loading,
    submitting,
    checking,
    connections,
    statuses,
    engineInput,
    labelInput,
    commandInput,
    argsInput,
    envInput,
    onEngineChange,
    onLabelChange,
    onCommandChange,
    onArgsChange,
    onEnvChange,
    onFillEnginePreset,
    onAddConnection,
    onUpdateConnection,
    onRemoveConnection,
    onCheckConnection,
    onCheckAll,
  } = props;

  const busy = loading || submitting || checking;
  const [activeGuide, setActiveGuide] = useState<EngineGuideKey | null>(null);
  const configuredEngines = new Set(connections.map((connection) => connection.engine));
  const missingEngines = MCP_ENGINE_OPTIONS.filter(
    (engine) => !configuredEngines.has(engine.value),
  );

  return (
    <>
      {activeGuide ? (
        <EngineInstallGuideModal
          engine={activeGuide}
          onClose={() => setActiveGuide(null)}
          onFillPreset={() => onFillEnginePreset(activeGuide)}
        />
      ) : null}
      <div className="settings-detail-stack settings-detail-stack--fill">
      <section className="settings-pane-card settings-pane-card-main settings-engine-whole">
        <div className="settings-card-head">
          <h2 className="settings-card-title">引擎连接</h2>
          <div className="settings-card-actions">
            <span className="settings-chip">{connections.length} 项</span>
            <button
              type="button"
              className="settings-pill-button"
              disabled={busy || !connections.length}
              onClick={onCheckAll}
            >
              {checking ? "检查中..." : "检查全部"}
            </button>
          </div>
        </div>

        <div className="settings-engine-grid">
          <div className="settings-engine-list">
            {connections.map((connection) => {
                const status = statuses[connection.id];
                const guideEngine = hasInstallGuide(connection.engine) ? connection.engine : null;
                return (
                  <article key={connection.id} className="settings-engine-card">
                    <div className="settings-engine-card-head">
                      <div>
                        <h3>{connection.label}</h3>
                        <span>{connection.engine}</span>
                      </div>
                      <span className={`settings-chip ${mcpStatusClass(status)}`}>
                        {mcpStatusLabel(status)}
                      </span>
                    </div>

                    <div className="settings-engine-command">
                      <code>{connection.command || "未填写启动命令"}</code>
                      {connection.args.length ? (
                        <small>{connection.args.join(" ")}</small>
                      ) : null}
                    </div>

                    {status?.message ? (
                      <p className="settings-engine-message">{status.message}</p>
                    ) : null}

                    {status?.tools?.length ? (
                      <div className="settings-engine-tools">
                        {status.tools.slice(0, 12).map((tool) => (
                          <span key={tool.name} className="settings-chip subtle">
                            {tool.name}
                          </span>
                        ))}
                        {status.tools.length > 12 ? (
                          <span className="settings-chip subtle">
                            +{status.tools.length - 12}
                          </span>
                        ) : null}
                      </div>
                    ) : null}

                    <div className="settings-engine-actions">
                      {guideEngine ? (
                        <button
                          type="button"
                          className="settings-pill-button"
                          onClick={() => setActiveGuide(guideEngine)}
                        >
                          安装指引
                        </button>
                      ) : null}
                      <label className="settings-toggle compact">
                        <input
                          type="checkbox"
                          checked={connection.enabled}
                          disabled={busy}
                          onChange={(event) =>
                            onUpdateConnection(connection.id, {
                              enabled: event.target.checked,
                            })
                          }
                        />
                        <span>启用</span>
                      </label>
                      <button
                        type="button"
                        className="settings-pill-button"
                        disabled={busy || !connection.command}
                        onClick={() => onCheckConnection(connection.id)}
                      >
                        检查
                      </button>
                      <button
                        type="button"
                        className="settings-pill-button danger"
                        disabled={busy}
                        onClick={() => onRemoveConnection(connection.id)}
                      >
                        移除
                      </button>
                    </div>
                  </article>
                );
              })}
            {missingEngines.map((engine) => {
              const guideEngine = hasInstallGuide(engine.value) ? engine.value : null;
              return (
              <article key={engine.value} className="settings-engine-card is-empty">
                <div className="settings-engine-card-head">
                  <div>
                    <h3>{engine.label}</h3>
                    <span>{engine.value}</span>
                  </div>
                  <span className="settings-chip muted">未配置</span>
                </div>
                <p className="settings-engine-message">
                  尚未为当前项目配置 {engine.label} MCP。填写右侧表单后可进行健康检查。
                </p>
                {guideEngine ? (
                  <div className="settings-engine-actions align-right">
                    <button
                      type="button"
                      className="settings-pill-button"
                      onClick={() => setActiveGuide(guideEngine)}
                    >
                      安装指引
                    </button>
                  </div>
                ) : null}
              </article>
              );
            })}
          </div>

          <div className="settings-engine-form">
            <div className="settings-card-head compact">
              <h2 className="settings-card-title">添加 MCP</h2>
            </div>
            <div className="settings-form">
              <label className="settings-field">
                <span>引擎</span>
                <select
                  value={engineInput}
                  disabled={busy}
                  onChange={(event) =>
                    onEngineChange(event.target.value as McpConnectionConfig["engine"])
                  }
                >
                  {MCP_ENGINE_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="settings-field">
                <span>显示名称</span>
                <input
                  value={labelInput}
                  disabled={busy}
                  onChange={(event) => onLabelChange(event.target.value)}
                  placeholder="例如：主引擎 MCP"
                />
              </label>
              <label className="settings-field">
                <span>启动命令</span>
                <input
                  value={commandInput}
                  disabled={busy}
                  onChange={(event) => onCommandChange(event.target.value)}
                  placeholder="例如：npx / uv / python"
                />
              </label>
              <label className="settings-field">
                <span>启动参数，每行一个</span>
                <textarea
                  value={argsInput}
                  disabled={busy}
                  onChange={(event) => onArgsChange(event.target.value)}
                  placeholder={"例如：\n@coding-solo/godot-mcp"}
                />
              </label>
              <label className="settings-field">
                <span>环境变量，每行 KEY=VALUE</span>
                <textarea
                  value={envInput}
                  disabled={busy}
                  onChange={(event) => onEnvChange(event.target.value)}
                  placeholder={"例如：\nGODOT_PATH=E:\\Tools\\Godot.exe"}
                />
              </label>
              <button
                type="button"
                className="settings-primary-button"
                disabled={busy}
                onClick={onAddConnection}
              >
                保存连接
              </button>
            </div>
          </div>
        </div>
      </section>
      </div>
    </>
  );
}

interface WorkspacesSectionProps {
  loading: boolean;
  submitting: boolean;
  workspaces: ProjectWorkspace[];
  labelInput: string;
  kindInput: string;
  pathInput: string;
  writableInput: boolean;
  onLabelChange: (value: string) => void;
  onKindChange: (value: string) => void;
  onPathChange: (value: string) => void;
  onWritableChange: (value: boolean) => void;
  onAddWorkspace: () => void;
  onRemoveWorkspace: (workspace: ProjectWorkspace) => void;
}

export function WorkspacesSection(props: WorkspacesSectionProps) {
  const {
    loading,
    submitting,
    workspaces,
    labelInput,
    kindInput,
    pathInput,
    writableInput,
    onLabelChange,
    onKindChange,
    onPathChange,
    onWritableChange,
    onAddWorkspace,
    onRemoveWorkspace,
  } = props;

  const workspaceList = (() => {
    if (loading) {
      return <div className="settings-empty">正在加载工作区列表...</div>;
    }

    if (!workspaces.length) {
      return (
        <div className="settings-empty">
          当前项目还没有工作区。你可以在右侧添加 Generic、Unity、Godot 或 Blender 工作区。
        </div>
      );
    }

    return (
      <div className="workspace-list">
        {workspaces.map((workspace) => (
          <div key={workspace.id} className="workspace-card">
            <div className="workspace-card-main">
              <div className="workspace-card-head">
                <div className="workspace-title-block">
                  <div className="workspace-title-row">
                    <h3>{workspace.label}</h3>
                    <span className="settings-chip">{kindLabel(workspace.kind)}</span>
                    <span className="settings-chip subtle">
                      {workspace.writable ? "可写" : "只读"}
                    </span>
                    {!workspace.enabled ? (
                      <span className="settings-chip subtle">已停用</span>
                    ) : null}
                  </div>
                  <div className="workspace-source">{sourceLabel(workspace.source)}</div>
                </div>
                <button
                  type="button"
                  className="settings-pill-button danger"
                  onClick={() => onRemoveWorkspace(workspace)}
                >
                  移除
                </button>
              </div>
              <div className="workspace-path">{workspace.root}</div>
            </div>
          </div>
        ))}
      </div>
    );
  })();

  return (
    <div className="settings-detail-stack settings-detail-stack--fill">
      <article className="settings-pane-card settings-workspace-whole">
        <div className="settings-workspace-split">
          <div className="settings-workspace-left">
            <div className="settings-card-head">
              <h2 className="settings-card-title">当前工作区</h2>
              <span className="settings-chip">{workspaces.length} 项</span>
            </div>
            {workspaceList}
          </div>

          <div className="settings-workspace-right">
            <div className="settings-card-head compact">
              <h2 className="settings-card-title">添加工作区</h2>
            </div>
            <div className="settings-form">
              <label className="settings-field">
                <span>显示名称</span>
                <input
                  type="text"
                  value={labelInput}
                  onChange={(event) => onLabelChange(event.target.value)}
                  placeholder="例如：主游戏工程"
                />
              </label>

              <label className="settings-field">
                <span>工作区类型</span>
                <select
                  value={kindInput}
                  onChange={(event) => onKindChange(event.target.value)}
                >
                  {WORKSPACE_KIND_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>

              <label className="settings-field">
                <span>目录路径</span>
                <input
                  type="text"
                  value={pathInput}
                  onChange={(event) => onPathChange(event.target.value)}
                  placeholder="输入本地目录绝对路径"
                />
              </label>

              <label className="settings-toggle">
                <input
                  type="checkbox"
                  checked={writableInput}
                  onChange={(event) => onWritableChange(event.target.checked)}
                />
                <span>允许后续受控写入</span>
              </label>

              <button
                type="button"
                className="settings-primary-button"
                disabled={submitting}
                onClick={onAddWorkspace}
              >
                添加工作区
              </button>
            </div>
          </div>
        </div>
      </article>
    </div>
  );
}

interface HistorySectionProps {
  archivedProjects: ProjectMeta[];
  projectUpdated: (project: ProjectMeta | undefined) => string;
  onRestoreProject: (project: ProjectMeta) => void;
  onDeleteProject: (project: ProjectMeta) => void;
}

export function HistorySection(props: HistorySectionProps) {
  const { archivedProjects, projectUpdated, onRestoreProject, onDeleteProject } =
    props;

  return (
    <div className="settings-detail-stack settings-detail-stack--fill">
      <section className="settings-pane-card settings-pane-card-main settings-history-whole">
        <div className="settings-card-head">
          <h2 className="settings-card-title">项目历史</h2>
          <span className="settings-chip">{archivedProjects.length} 项</span>
        </div>
        {!archivedProjects.length ? (
          <div className="settings-empty">当前还没有历史项目。</div>
        ) : (
          <div className="workspace-list">
            {archivedProjects.map((project) => (
              <div key={project.id} className="workspace-card">
                <div className="workspace-card-main">
                  <div className="workspace-card-head">
                    <div className="workspace-title-block">
                      <div className="workspace-title-row">
                        <h3>{project.display_name || project.id}</h3>
                        <span className="settings-chip subtle">已归档</span>
                      </div>
                      <div className="workspace-source">
                        {(project.last_phase || "暂无阶段") +
                          " · " +
                          projectUpdated(project)}
                      </div>
                    </div>
                    <div className="workspace-actions">
                      <button
                        type="button"
                        className="settings-pill-button"
                        onClick={() => onRestoreProject(project)}
                      >
                        恢复
                      </button>
                      <button
                        type="button"
                        className="settings-pill-button danger"
                        onClick={() => onDeleteProject(project)}
                      >
                        删除
                      </button>
                    </div>
                  </div>
                  <div className="workspace-path">
                    {project.last_message_preview || "暂无 Agent 回复摘要。"}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
