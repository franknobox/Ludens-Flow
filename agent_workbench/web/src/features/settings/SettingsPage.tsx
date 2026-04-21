import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";

import { workbenchApi } from "../workbench/api";
import { PHASE_LABEL } from "../workbench/constants";
import { useProjectRuntime } from "../workbench/state/ProjectRuntimeContext";
import { projectUpdated, toErrorMessage } from "../workbench/utils";
import type {
  ProjectMeta,
  ProjectSettingsResponse,
  ProjectWorkspace,
  ToolCatalogItem,
} from "../workbench/types";

const MODEL_ROUTING_TEMPLATE = {
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

const WORKSPACE_KIND_OPTIONS = [
  { value: "unity", label: "Unity" },
  { value: "generic", label: "Generic" },
  { value: "blender", label: "Blender" },
];

const SETTINGS_SECTIONS = [
  { id: "general", label: "通用设置", hint: "写入总开关" },
  { id: "tools", label: "工具", hint: "能力目录" },
  { id: "workspaces", label: "工作区清单", hint: "目录与权限" },
  { id: "history", label: "历史项目", hint: "归档与恢复" },
] as const;

type SettingsSectionId = (typeof SETTINGS_SECTIONS)[number]["id"];

interface SettingsPageProps {
  isActive?: boolean;
}

function normalizeWorkspacePathInput(value: string): string {
  const trimmed = value.trim();
  if (
    trimmed.length >= 2 &&
    trimmed[0] === trimmed[trimmed.length - 1] &&
    (trimmed[0] === '"' || trimmed[0] === "'")
  ) {
    return trimmed.slice(1, -1).trim();
  }
  return trimmed;
}

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

export function SettingsPage({ isActive = false }: SettingsPageProps) {
  const {
    runtimeState,
    projects,
    activeProjects,
    archivedProjects,
    refreshRuntime,
    selectProject,
    createProject: createRuntimeProject,
  } = useProjectRuntime();

  const [workspaces, setWorkspaces] = useState<ProjectWorkspace[]>([]);
  const [tools, setTools] = useState<ToolCatalogItem[]>([]);
  const [projectSettings, setProjectSettings] =
    useState<ProjectSettingsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [settingsSubmitting, setSettingsSubmitting] = useState(false);
  const [errorText, setErrorText] = useState("");
  const [successText, setSuccessText] = useState("");
  const [activeSection, setActiveSection] =
    useState<SettingsSectionId>("general");
  const [labelInput, setLabelInput] = useState("");
  const [kindInput, setKindInput] = useState("unity");
  const [pathInput, setPathInput] = useState("");
  const [writableInput, setWritableInput] = useState(false);
  const [topbarSlot, setTopbarSlot] = useState<HTMLElement | null>(null);
  const [projectPanelOpen, setProjectPanelOpen] = useState(false);
  const [projectCreateMode, setProjectCreateMode] = useState(false);
  const [projectTitleDraft, setProjectTitleDraft] = useState("");
  const [modelRoutingDraft, setModelRoutingDraft] = useState("{}");
  const [modelRoutingDirty, setModelRoutingDirty] = useState(false);
  const [modelRoutingProjectId, setModelRoutingProjectId] = useState("");

  const projectPanelRef = useRef<HTMLDivElement>(null);
  const projectPanelButtonRef = useRef<HTMLButtonElement>(null);

  const activeProject = useMemo(
    () => projects.find((project) => project.id === runtimeState?.project_id),
    [projects, runtimeState?.project_id],
  );

  const toolsByCategory = useMemo(
    () =>
      tools.reduce<Record<string, ToolCatalogItem[]>>((acc, tool) => {
        const key = tool.category || "general";
        if (!acc[key]) acc[key] = [];
        acc[key]!.push(tool);
        return acc;
      }, {}),
    [tools],
  );

  const phaseLabel =
    PHASE_LABEL[runtimeState?.phase || ""] || runtimeState?.phase || "未开始";
  const currentProjectName =
    activeProject?.display_name || activeProject?.title || "未选择项目";

  const clearMessages = () => {
    setErrorText("");
    setSuccessText("");
  };

  const modelRoutingValidation = useMemo(() => {
    const raw = modelRoutingDraft.trim();
    if (!raw) {
      return {
        parsed: {},
        normalized: "{}",
        error: "",
      } as const;
    }

    try {
      const parsed = JSON.parse(raw) as unknown;
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
        return {
          parsed: null,
          normalized: "",
          error: "模型路由必须是 JSON 对象，不能是数组或基础类型。",
        } as const;
      }

      return {
        parsed: parsed as Record<string, unknown>,
        normalized: JSON.stringify(parsed),
        error: "",
      } as const;
    } catch (error) {
      return {
        parsed: null,
        normalized: "",
        error: `JSON 格式错误：${toErrorMessage(error)}`,
      } as const;
    }
  }, [modelRoutingDraft]);

  const refresh = async () => {
    setLoading(true);
    setErrorText("");
    try {
      await refreshRuntime();

      const [workspacesResult, toolsResult, projectSettingsResult] =
        await Promise.allSettled([
          workbenchApi.getCurrentWorkspaces(),
          workbenchApi.getTools(),
          workbenchApi.getCurrentProjectSettings(),
        ]);

      if (workspacesResult.status === "fulfilled") {
        setWorkspaces(workspacesResult.value.workspaces || []);
      } else {
        setWorkspaces([]);
      }

      if (toolsResult.status === "fulfilled") {
        setTools(toolsResult.value.tools || []);
      } else {
        setTools([]);
      }

      if (projectSettingsResult.status === "fulfilled") {
        setProjectSettings(projectSettingsResult.value);
      } else {
        setProjectSettings({
          project_id: runtimeState?.project_id || "",
          agent_file_write_enabled: true,
        });
      }
    } catch (error) {
      setErrorText(toErrorMessage(error));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    setTopbarSlot(document.getElementById("topbar-center-slot"));
  }, []);

  useEffect(() => {
    void refresh();
  }, []);

  useEffect(() => {
    if (!isActive) return;
    void refresh();
  }, [isActive]);

  useEffect(() => {
    if (!projectSettings) return;

    const sourceProjectId = projectSettings.project_id || "";
    const sourceDraft = JSON.stringify(
      projectSettings.model_routing || {},
      null,
      2,
    );

    const switchedProject = modelRoutingProjectId !== sourceProjectId;
    if (switchedProject || !modelRoutingDirty) {
      setModelRoutingDraft(sourceDraft);
      setModelRoutingDirty(false);
      setModelRoutingProjectId(sourceProjectId);
    }
  }, [projectSettings, modelRoutingDirty, modelRoutingProjectId]);

  useEffect(() => {
    if (!projectPanelOpen) return;

    const handlePointerDown = (event: MouseEvent) => {
      const target = event.target as Node | null;
      if (
        projectPanelRef.current?.contains(target) ||
        projectPanelButtonRef.current?.contains(target)
      ) {
        return;
      }
      setProjectPanelOpen(false);
      setProjectCreateMode(false);
      setProjectTitleDraft("");
    };

    document.addEventListener("mousedown", handlePointerDown);
    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
    };
  }, [projectPanelOpen]);

  const closeProjectPanel = () => {
    setProjectPanelOpen(false);
    setProjectCreateMode(false);
    setProjectTitleDraft("");
  };

  const openProject = async (projectId: string) => {
    if (!projectId) return;
    clearMessages();
    try {
      await selectProject(projectId);
      closeProjectPanel();
      void refresh();
    } catch (error) {
      setErrorText(toErrorMessage(error));
    }
  };

  const createProject = async (title: string) => {
    const trimmed = title.trim();
    if (!trimmed) {
      setErrorText("请输入项目名称。");
      return;
    }
    clearMessages();
    try {
      await createRuntimeProject(trimmed);
      closeProjectPanel();
      void refresh();
    } catch (error) {
      setErrorText(toErrorMessage(error));
    }
  };

  const handleAddWorkspace = async () => {
    const root = normalizeWorkspacePathInput(pathInput);
    if (!root) {
      setErrorText("请先输入工作区目录路径。");
      setActiveSection("workspaces");
      return;
    }

    setSubmitting(true);
    clearMessages();
    try {
      const response = await workbenchApi.addCurrentWorkspace({
        root,
        kind: kindInput,
        label: labelInput.trim() || null,
        writable: writableInput,
        enabled: true,
      });
      setWorkspaces(response.workspaces || []);
      setLabelInput("");
      setPathInput("");
      setWritableInput(false);
      setSuccessText("工作区已加入当前项目。");
      setActiveSection("workspaces");
    } catch (error) {
      setErrorText(toErrorMessage(error));
      setActiveSection("workspaces");
    } finally {
      setSubmitting(false);
    }
  };

  const handleRemoveWorkspace = async (workspace: ProjectWorkspace) => {
    const confirmed = window.confirm(
      `要将“${workspace.label}”从当前项目的工作区清单中移除吗？\n\n这不会删除本地目录，只会移出允许访问列表。`,
    );
    if (!confirmed) return;

    clearMessages();
    try {
      const response = await workbenchApi.deleteCurrentWorkspace(workspace.id);
      setWorkspaces(response.workspaces || []);
      setSuccessText("工作区已移除。");
    } catch (error) {
      setErrorText(toErrorMessage(error));
    }
  };

  const handleRestoreProject = async (project: ProjectMeta) => {
    const confirmed = window.confirm(
      `要恢复“${project.display_name || project.id}”吗？\n\n恢复后它会重新出现在当前项目列表中。`,
    );
    if (!confirmed) return;

    clearMessages();
    try {
      await workbenchApi.restoreProject(project.id, false);
      setSuccessText("项目已恢复。");
      await refresh();
    } catch (error) {
      setErrorText(toErrorMessage(error));
    }
  };

  const handleDeleteProject = async (project: ProjectMeta) => {
    const confirmed = window.confirm(
      `要永久删除“${project.display_name || project.id}”吗？\n\n这会删除该项目的目录和数据，而且无法撤销。`,
    );
    if (!confirmed) return;

    clearMessages();
    try {
      await workbenchApi.deleteProject(project.id);
      setSuccessText("项目已删除。");
      await refresh();
    } catch (error) {
      setErrorText(toErrorMessage(error));
    }
  };

  const handleToggleFileWrite = async (enabled: boolean) => {
    setSettingsSubmitting(true);
    clearMessages();
    try {
      const response = await workbenchApi.updateCurrentProjectSettings({
        agent_file_write_enabled: enabled,
      });
      setProjectSettings(response);
      setSuccessText(enabled ? "已开启 Agent 文件写入。" : "已关闭 Agent 文件写入。");
    } catch (error) {
      setErrorText(toErrorMessage(error));
    } finally {
      setSettingsSubmitting(false);
    }
  };

  const handleSaveModelRouting = async () => {
    if (modelRoutingValidation.error || !modelRoutingValidation.parsed) {
      setErrorText(modelRoutingValidation.error || "模型路由配置无效，无法保存。");
      setActiveSection("general");
      return;
    }

    setSettingsSubmitting(true);
    clearMessages();
    try {
      const response = await workbenchApi.updateCurrentProjectSettings({
        model_routing: modelRoutingValidation.parsed,
      });
      setProjectSettings(response);
      setModelRoutingDraft(
        JSON.stringify(response.model_routing || {}, null, 2),
      );
      setModelRoutingDirty(false);
      setSuccessText("模型路由已保存。新请求会按新路由生效。");
    } catch (error) {
      setErrorText(toErrorMessage(error));
    } finally {
      setSettingsSubmitting(false);
    }
  };

  const topbarProjectNode =
    isActive && topbarSlot
      ? createPortal(
          <div className="project-toolbar">
            <div className="project-toolbar-info">
              <div className="project-toolbar-meta">
                <span className="project-toolbar-label">项目名</span>
                <strong>{currentProjectName}</strong>
              </div>
              <div className="project-toolbar-meta">
                <span className="project-toolbar-label">项目阶段</span>
                <strong>{phaseLabel}</strong>
              </div>
              <div className="project-toolbar-meta">
                <span className="project-toolbar-label">更新时间</span>
                <strong>{projectUpdated(activeProject)}</strong>
              </div>
            </div>

            <div className="project-toolbar-menu">
              <button
                ref={projectPanelButtonRef}
                type="button"
                className={`project-toolbar-toggle${projectPanelOpen ? " is-active" : ""}`}
                onClick={() => {
                  if (projectPanelOpen) {
                    closeProjectPanel();
                    return;
                  }
                  setProjectPanelOpen(true);
                }}
              >
                项目选单
              </button>

              {projectPanelOpen ? (
                <div ref={projectPanelRef} className="project-toolbar-panel">
                  {!projectCreateMode ? (
                    <>
                      <div className="project-toolbar-panel-title">切换项目</div>
                      <div className="project-toolbar-list">
                        {activeProjects.map((project) => (
                          <button
                            key={project.id}
                            type="button"
                            className={`project-toolbar-item${
                              project.id === runtimeState?.project_id ? " is-active" : ""
                            }`}
                            onClick={() => {
                              void openProject(project.id);
                            }}
                          >
                            <div className="project-toolbar-item-head">
                              <strong className="project-toolbar-item-name">
                                {project.display_name || project.id}
                              </strong>
                              <div className="project-toolbar-item-meta-row">
                                <span className="project-toolbar-item-sub">
                                  {PHASE_LABEL[
                                    project.id === runtimeState?.project_id
                                      ? runtimeState?.phase || project.last_phase || ""
                                      : project.last_phase || ""
                                  ] ||
                                    (project.id === runtimeState?.project_id
                                      ? runtimeState?.phase || project.last_phase || "暂无阶段"
                                      : project.last_phase || "暂无阶段")}
                                </span>
                                <span className="project-toolbar-item-sub">
                                  {projectUpdated(project)}
                                </span>
                              </div>
                              {project.id === runtimeState?.project_id ? (
                                <span className="tag active">当前</span>
                              ) : null}
                            </div>
                          </button>
                        ))}
                      </div>
                      <button
                        type="button"
                        className="project-toolbar-create-entry"
                        onClick={() => {
                          setProjectCreateMode(true);
                          setProjectTitleDraft("");
                        }}
                      >
                        <span>新建项目</span>
                        <span className="project-toolbar-create-plus">+</span>
                      </button>
                    </>
                  ) : (
                    <div className="project-toolbar-create">
                      <div className="project-toolbar-panel-title">新建项目</div>
                      <input
                        value={projectTitleDraft}
                        onChange={(event) => setProjectTitleDraft(event.target.value)}
                        type="text"
                        placeholder="输入项目名称"
                        autoFocus
                      />
                      <div className="project-toolbar-create-actions">
                        <button
                          type="button"
                          className="shell-btn primary"
                          onClick={() => {
                            void createProject(projectTitleDraft);
                          }}
                        >
                          确认新建
                        </button>
                        <button
                          type="button"
                          className="shell-btn"
                          onClick={() => {
                            setProjectCreateMode(false);
                            setProjectTitleDraft("");
                          }}
                        >
                          取消
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              ) : null}
            </div>
          </div>,
          topbarSlot,
        )
      : null;

  const renderGeneral = () => (
    <div className="settings-detail-stack">
      <section className="settings-pane-card settings-pane-card-main">
        <div className="settings-card-head">
          <div>
            <h2 className="settings-card-title">通用设置</h2>
          </div>
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
              onChange={(event) => {
                void handleToggleFileWrite(event.target.checked);
              }}
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
      </section>

      <section className="settings-pane-card settings-pane-card-main">
        <div className="settings-card-head">
          <div>
            <h2 className="settings-card-title">模型路由</h2>
          </div>
          <span className="settings-chip">
            {modelRoutingDirty ? "有未保存修改" : "已同步"}
          </span>
        </div>

        <div className="settings-form">
          <div className="settings-note-strip">
            <span className="settings-note-item">优先级：agent_capabilities</span>
            <span className="settings-note-item">{"> capabilities > agents > global"}</span>
            <span className="settings-note-item">最后回退到 .env 默认模型</span>
          </div>

          <div className="settings-route-actions">
            <button
              type="button"
              className="settings-pill-button"
              disabled={settingsSubmitting}
              onClick={() => {
                setModelRoutingDraft(
                  JSON.stringify(MODEL_ROUTING_TEMPLATE, null, 2),
                );
                setModelRoutingDirty(true);
                clearMessages();
              }}
            >
              填入推荐模板
            </button>
            <button
              type="button"
              className="settings-pill-button"
              disabled={settingsSubmitting}
              onClick={() => {
                setModelRoutingDraft("{}");
                setModelRoutingDirty(true);
                clearMessages();
              }}
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
              onChange={(event) => {
                setModelRoutingDraft(event.target.value);
                setModelRoutingDirty(true);
              }}
              spellCheck={false}
              placeholder='例如：{"global":{"provider":"openai","model":"gpt-4o-mini"}}'
            />
          </label>

          {modelRoutingValidation.error ? (
            <div className="settings-inline-error">{modelRoutingValidation.error}</div>
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
            onClick={() => {
              void handleSaveModelRouting();
            }}
          >
            保存模型路由
          </button>
        </div>
      </section>
    </div>
  );

  const renderOverview = () => (
    <div className="settings-detail-stack">
      <section className="settings-pane-card settings-pane-card-main">
        <div className="settings-card-head">
          <div>
            <h2 className="settings-card-title">项目概览</h2>
          </div>
          <button
            type="button"
            className="settings-pill-button"
            onClick={() => {
              void refresh();
            }}
            disabled={loading}
          >
            刷新
          </button>
        </div>

        <div className="settings-inline-stats">
          <div className="settings-inline-stat">
            <span className="settings-stat-label">项目名称</span>
            <strong>{currentProjectName}</strong>
          </div>
          <div className="settings-inline-stat">
            <span className="settings-stat-label">当前阶段</span>
            <strong>{phaseLabel}</strong>
          </div>
          <div className="settings-inline-stat">
            <span className="settings-stat-label">工作区数量</span>
            <strong>{workspaces.length}</strong>
          </div>
          <div className="settings-inline-stat">
            <span className="settings-stat-label">工具总数</span>
            <strong>{tools.length}</strong>
          </div>
          <div className="settings-inline-stat wide">
            <span className="settings-stat-label">最近更新时间</span>
            <strong>{projectUpdated(activeProject)}</strong>
          </div>
        </div>

        <div className="settings-note-strip">
          <span className="settings-note-item">Agent 只能访问已加入清单的目录</span>
          <span className="settings-note-item">工作区边界由你手动维护</span>
          <span className="settings-note-item">可写工作区建议按需开启</span>
        </div>
      </section>
    </div>
  );

  const renderTools = () => (
    <div className="settings-detail-stack tools-detail-stack">
      <section className="settings-pane-card settings-pane-card-main settings-pane-scroll-frame">
        <div className="settings-card-head">
          <div>
            <h2 className="settings-card-title">工具目录</h2>
          </div>
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

  const renderWorkspaceList = () => {
    if (loading) {
      return <div className="settings-empty">正在加载工作区列表…</div>;
    }

    if (!workspaces.length) {
      return (
        <div className="settings-empty">
          当前项目还没有工作区。你可以在右侧添加 Unity、Generic 或 Blender
          工作区。
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
                  onClick={() => {
                    void handleRemoveWorkspace(workspace);
                  }}
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
  };

  const renderWorkspaces = () => (
    <div className="settings-detail-stack">
      <section className="settings-workspace-layout">
        <article className="settings-pane-card settings-pane-card-main">
          <div className="settings-card-head">
            <div>
              <h2 className="settings-card-title">当前工作区</h2>
            </div>
            <span className="settings-chip">{workspaces.length} 项</span>
          </div>
          {renderWorkspaceList()}
        </article>

        <article className="settings-pane-card settings-pane-card-side">
          <div className="settings-card-head compact">
            <div>
              <h2 className="settings-card-title">添加工作区</h2>
            </div>
          </div>
          <div className="settings-form">
            <label className="settings-field">
              <span>显示名称</span>
              <input
                type="text"
                value={labelInput}
                onChange={(event) => setLabelInput(event.target.value)}
                placeholder="例如：主 Unity 工程"
              />
            </label>

            <label className="settings-field">
              <span>工作区类型</span>
              <select
                value={kindInput}
                onChange={(event) => setKindInput(event.target.value)}
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
                onChange={(event) => setPathInput(event.target.value)}
                placeholder="输入本地目录绝对路径"
              />
            </label>

            <label className="settings-toggle">
              <input
                type="checkbox"
                checked={writableInput}
                onChange={(event) => setWritableInput(event.target.checked)}
              />
              <span>允许后续受控写入</span>
            </label>

            <button
              type="button"
              className="settings-primary-button"
              disabled={submitting}
              onClick={() => {
                void handleAddWorkspace();
              }}
            >
              添加工作区
            </button>
          </div>
        </article>
      </section>
    </div>
  );

  const renderHistory = () => (
    <div className="settings-detail-stack">
      <section className="settings-pane-card settings-pane-card-main">
        <div className="settings-card-head">
          <div>
            <h2 className="settings-card-title">项目历史</h2>
          </div>
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
                        onClick={() => {
                          void handleRestoreProject(project);
                        }}
                      >
                        恢复
                      </button>
                      <button
                        type="button"
                        className="settings-pill-button danger"
                        onClick={() => {
                          void handleDeleteProject(project);
                        }}
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

  return (
    <>
      {topbarProjectNode}
      <div className="settings-page">
        <aside className="settings-sidebar">
          <nav className="settings-nav" aria-label="设置目录">
            {SETTINGS_SECTIONS.map((section) => {
              const isCurrent = activeSection === section.id;
              return (
                <button
                  key={section.id}
                  type="button"
                  className={`settings-nav-item${isCurrent ? " is-active" : ""}`}
                  onClick={() => {
                    clearMessages();
                    setActiveSection(section.id);
                  }}
                >
                  <span className="settings-nav-label">{section.label}</span>
                  <span className="settings-nav-text">{section.hint}</span>
                </button>
              );
            })}
          </nav>
        </aside>

        <main className="settings-detail">
          {activeSection === "general" ? renderGeneral() : null}
          {activeSection === "tools" ? renderTools() : null}
          {activeSection === "workspaces" ? renderWorkspaces() : null}
          {activeSection === "history" ? renderHistory() : null}
          {successText ? (
            <div className="settings-feedback success">{successText}</div>
          ) : null}
          {errorText ? (
            <div className="settings-feedback error">{errorText}</div>
          ) : null}
        </main>
      </div>
    </>
  );
}
