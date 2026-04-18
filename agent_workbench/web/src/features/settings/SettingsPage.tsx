import { useEffect, useMemo, useState } from "react";

import { workbenchApi } from "../workbench/api";
import { PHASE_LABEL } from "../workbench/constants";
import { projectUpdated, toErrorMessage } from "../workbench/utils";
import type { ProjectMeta, ProjectWorkspace, StateResponse } from "../workbench/types";

const WORKSPACE_KIND_OPTIONS = [
  { value: "unity", label: "Unity" },
  { value: "generic", label: "Generic" },
  { value: "blender", label: "Blender" },
];

const SETTINGS_SECTIONS = [
  {
    id: "overview",
    label: "项目概览",
    description: "查看当前项目状态与访问边界说明。",
  },
  {
    id: "workspaces",
    label: "工作区清单",
    description: "管理允许 Agent 读取或操作的目录范围。",
  },
  {
    id: "history",
    label: "历史项目",
    description: "查看已归档项目，并执行恢复或删除。",
  },
] as const;

type SettingsSectionId = (typeof SETTINGS_SECTIONS)[number]["id"];

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

interface SettingsPageProps {
  isActive?: boolean;
}

export function SettingsPage({ isActive = false }: SettingsPageProps) {
  const [state, setState] = useState<StateResponse | null>(null);
  const [projects, setProjects] = useState<ProjectMeta[]>([]);
  const [workspaces, setWorkspaces] = useState<ProjectWorkspace[]>([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [errorText, setErrorText] = useState("");
  const [successText, setSuccessText] = useState("");
  const [activeSection, setActiveSection] = useState<SettingsSectionId>("overview");
  const [labelInput, setLabelInput] = useState("");
  const [kindInput, setKindInput] = useState("unity");
  const [pathInput, setPathInput] = useState("");
  const [writableInput, setWritableInput] = useState(false);

  const activeProject = useMemo(
    () => projects.find((project) => project.id === state?.project_id),
    [projects, state?.project_id],
  );
  const archivedProjects = useMemo(
    () => projects.filter((project) => project.archived),
    [projects],
  );

  const phaseLabel = PHASE_LABEL[state?.phase || ""] || state?.phase || "未开始";
  const currentProjectName =
    activeProject?.display_name || activeProject?.title || "未选择项目";

  const clearMessages = () => {
    setErrorText("");
    setSuccessText("");
  };

  const refresh = async () => {
    setLoading(true);
    setErrorText("");
    try {
      const [nextState, nextProjects, nextWorkspaces] = await Promise.all([
        workbenchApi.getState(),
        workbenchApi.getProjects(),
        workbenchApi.getCurrentWorkspaces(),
      ]);
      setState(nextState);
      setProjects(nextProjects.projects || []);
      setWorkspaces(nextWorkspaces.workspaces || []);
    } catch (error) {
      setErrorText(toErrorMessage(error));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void refresh();
  }, []);

  useEffect(() => {
    if (!isActive) return;
    void refresh();
  }, [isActive]);

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

  const renderOverview = () => (
    <div className="settings-detail-stack">
      <section className="settings-pane-card settings-pane-hero">
        <div className="settings-pane-head">
          <div>
            <div className="settings-kicker">项目设置</div>
            <h1 className="settings-pane-title">{currentProjectName}</h1>
            <p className="settings-pane-text">
              这里用于维护当前项目的访问边界与基础配置信息。Agent 只能读取或操作你明确加入工作区清单的目录，不会自行扩大访问范围。
            </p>
          </div>
          <button
            type="button"
            className="settings-pill-button"
            onClick={() => {
              void refresh();
            }}
            disabled={loading}
          >
            刷新设置
          </button>
        </div>
      </section>

      <section className="settings-overview-grid">
        <article className="settings-pane-card">
          <div className="settings-card-kicker">当前项目</div>
          <h2 className="settings-card-title">项目状态</h2>
          <div className="settings-stat-grid">
            <div className="settings-stat">
              <span className="settings-stat-label">项目名称</span>
              <strong>{currentProjectName}</strong>
            </div>
            <div className="settings-stat">
              <span className="settings-stat-label">当前阶段</span>
              <strong>{phaseLabel}</strong>
            </div>
            <div className="settings-stat">
              <span className="settings-stat-label">工作区数量</span>
              <strong>{workspaces.length}</strong>
            </div>
            <div className="settings-stat">
              <span className="settings-stat-label">最近更新</span>
              <strong>{projectUpdated(activeProject)}</strong>
            </div>
          </div>
          <div className="settings-note-strip">
            当前前端只要求输入项目名称，系统会在后台自动生成稳定的项目标识，不再要求手动填写项目 ID。
          </div>
        </article>

        <article className="settings-pane-card">
          <div className="settings-card-kicker">访问边界</div>
          <h2 className="settings-card-title">工作区规则</h2>
          <ul className="settings-bullets">
            <li>只有加入清单的目录，Agent 才能读取或操作。</li>
            <li>当前阶段由用户手动配置工作区，Agent 不能自行绑定目录。</li>
            <li>可写工作区用于后续受控写入能力，默认建议保持关闭。</li>
          </ul>
        </article>
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
      <section className="settings-pane-card settings-pane-hero">
        <div className="settings-pane-head">
          <div>
            <div className="settings-kicker">工作区清单</div>
            <h1 className="settings-pane-title">允许访问的目录</h1>
            <p className="settings-pane-text">
              这里列出当前项目允许 Agent 读取或操作的目录。你可以按项目需要添加 Unity、Generic 或 Blender 工作区。
            </p>
          </div>
          <span className="settings-chip">{workspaces.length} 项</span>
        </div>
      </section>

      <section className="settings-workspace-layout">
        <article className="settings-pane-card">
          <div className="settings-card-head">
            <div>
              <div className="settings-card-kicker">已批准目录</div>
              <h2 className="settings-card-title">当前工作区</h2>
            </div>
          </div>
          {renderWorkspaceList()}
        </article>

        <article className="settings-pane-card">
          <div className="settings-card-kicker">新增工作区</div>
          <h2 className="settings-card-title">加入当前项目</h2>
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
              <select value={kindInput} onChange={(event) => setKindInput(event.target.value)}>
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
      <section className="settings-pane-card settings-pane-hero">
        <div className="settings-pane-head">
          <div>
            <div className="settings-kicker">历史项目</div>
            <h1 className="settings-pane-title">已归档项目</h1>
            <p className="settings-pane-text">
              这里集中管理已经归档的项目。你可以恢复它们回到工作台，也可以在确认后永久删除。
            </p>
          </div>
          <span className="settings-chip">{archivedProjects.length} 项</span>
        </div>
      </section>

      <section className="settings-pane-card">
        <div className="settings-card-head">
          <div>
            <div className="settings-card-kicker">归档列表</div>
            <h2 className="settings-card-title">项目历史</h2>
          </div>
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
                        {project.last_phase || "暂无阶段"} · {projectUpdated(project)}
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
    <div className="settings-page">
      <aside className="settings-sidebar">
        <div className="settings-sidebar-head">
          <div className="settings-kicker">设置</div>
          <h1 className="settings-sidebar-title">项目设置</h1>
          <p className="settings-sidebar-text">
            通过左侧目录导航查看项目概览、工作区权限与历史项目，右侧展示当前设置项的详细内容。
          </p>
        </div>

        <nav className="settings-nav" aria-label="设置目录">
          {SETTINGS_SECTIONS.map((section) => {
            const isActiveSection = activeSection === section.id;
            return (
              <button
                key={section.id}
                type="button"
                className={`settings-nav-item${isActiveSection ? " is-active" : ""}`}
                onClick={() => {
                  clearMessages();
                  setActiveSection(section.id);
                }}
              >
                <span className="settings-nav-label">{section.label}</span>
                <span className="settings-nav-text">{section.description}</span>
              </button>
            );
          })}
        </nav>
      </aside>

      <main className="settings-detail">
        {activeSection === "overview" ? renderOverview() : null}
        {activeSection === "workspaces" ? renderWorkspaces() : null}
        {activeSection === "history" ? renderHistory() : null}
        {successText ? <div className="settings-feedback success">{successText}</div> : null}
        {errorText ? <div className="settings-feedback error">{errorText}</div> : null}
      </main>
    </div>
  );
}
