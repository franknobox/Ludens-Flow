import type {
  ProjectMeta,
  ProjectSettingsResponse,
  ProjectWorkspace,
  ToolCatalogItem,
} from "../../workbench/types";

export const WORKSPACE_KIND_OPTIONS = [
  { value: "unity", label: "Unity" },
  { value: "generic", label: "Generic" },
  { value: "blender", label: "Blender" },
];

export const MODEL_ROUTING_TEMPLATE = {
  global: {
    provider: "openai",
    model: "gpt-4o-mini",
    temperature: 0.2,
  },
  agents: {
    design: {
      model: "gpt-4o",
    },
    review: {
      model: "o4-mini",
    },
  },
  capabilities: {
    review_gate: {
      model: "o4-mini",
    },
  },
};

type ModelRoutingValidation = {
  parsed: Record<string, unknown> | null;
  normalized: string;
  error: string;
};

function kindLabel(kind: string): string {
  if (kind === "unity") return "Unity";
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
  theme: string;
  modelRoutingDraft: string;
  modelRoutingDirty: boolean;
  modelRoutingValidation: ModelRoutingValidation;
  onToggleFileWrite: (enabled: boolean) => void;
  onThemeChange: (theme: string) => void;
  onModelRoutingDraftChange: (value: string) => void;
  onUseModelRoutingTemplate: () => void;
  onClearModelRouting: () => void;
  onSaveModelRouting: () => void;
}

export function GeneralSettingsSection(props: GeneralSettingsSectionProps) {
  const {
    projectSettings,
    loading,
    settingsSubmitting,
    theme,
    modelRoutingDraft,
    modelRoutingDirty,
    modelRoutingValidation,
    onToggleFileWrite,
    onThemeChange,
    onModelRoutingDraftChange,
    onUseModelRoutingTemplate,
    onClearModelRouting,
    onSaveModelRouting,
  } = props;

  return (
    <div className="settings-detail-stack">
      <section className="settings-pane-card settings-pane-card-main">
        <div className="settings-card-head">
          <h2 className="settings-card-title">通用设置</h2>
          <span className="settings-chip">
            {projectSettings?.agent_file_write_enabled ? "已开启" : "已关闭"}
          </span>
        </div>

        <div className="settings-form">
          <label className="settings-toggle">
            <input
              type="checkbox"
              checked={projectSettings?.agent_file_write_enabled ?? true}
              disabled={loading || settingsSubmitting}
              onChange={(event) => onToggleFileWrite(event.target.checked)}
            />
            <span>允许 Agent 写入当前项目工作区中的文件</span>
          </label>

          <div className="settings-note-strip">
            <span className="settings-note-item">
              关闭后，创建目录、写入、补丁、删除等写入类工具会被拒绝
            </span>
            <span className="settings-note-item">
              开启后，仍然会继续受工作区可写权限约束
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

      <section className="settings-pane-card settings-pane-card-main">
        <div className="settings-card-head">
          <h2 className="settings-card-title">模型路由</h2>
          <span className="settings-chip">
            {modelRoutingDirty ? "有未保存修改" : "已同步"}
          </span>
        </div>

        <div className="settings-form">
          <div className="settings-note-strip">
            <span className="settings-note-item">优先级：agent_capabilities</span>
            <span className="settings-note-item">
              {"> capabilities > agents > global"}
            </span>
            <span className="settings-note-item">最后回退到 .env 默认模型</span>
          </div>

          <div className="settings-route-actions">
            <button
              type="button"
              className="settings-pill-button"
              disabled={settingsSubmitting}
              onClick={onUseModelRoutingTemplate}
            >
              填入推荐模板
            </button>
            <button
              type="button"
              className="settings-pill-button"
              disabled={settingsSubmitting}
              onClick={onClearModelRouting}
            >
              清空为全局默认
            </button>
          </div>

          <label className="settings-field">
            <span>model_routing（JSON）</span>
            <textarea
              className={`settings-json-editor${
                modelRoutingValidation.error ? " is-invalid" : ""
              }`}
              value={modelRoutingDraft}
              onChange={(event) => onModelRoutingDraftChange(event.target.value)}
              spellCheck={false}
              placeholder='例如：{"global":{"provider":"openai","model":"gpt-4o-mini"}}'
            />
          </label>

          {modelRoutingValidation.error ? (
            <div className="settings-inline-error">
              {modelRoutingValidation.error}
            </div>
          ) : (
            <div className="settings-inline-help">
              支持字段：`global` / `agents` / `capabilities` / `agent_capabilities`。
            </div>
          )}

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
        </div>
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
          当前项目还没有工作区。你可以在右侧添加 Unity、Generic 或 Blender 工作区。
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
    <div className="settings-detail-stack">
      <section className="settings-workspace-layout">
        <article className="settings-pane-card settings-pane-card-main">
          <div className="settings-card-head">
            <h2 className="settings-card-title">当前工作区</h2>
            <span className="settings-chip">{workspaces.length} 项</span>
          </div>
          {workspaceList}
        </article>

        <article className="settings-pane-card settings-pane-card-side">
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
                placeholder="例如：主 Unity 工程"
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
        </article>
      </section>
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
    <div className="settings-detail-stack">
      <section className="settings-pane-card settings-pane-card-main">
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
