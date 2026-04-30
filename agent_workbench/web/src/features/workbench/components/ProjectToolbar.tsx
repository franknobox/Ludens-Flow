import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

import type { McpTool } from "../types";
import { MCP_ICONS } from "../../mcp/components/McpIcons";

import { PHASE_LABEL } from "../constants";
import { projectUpdated } from "../utils";
import type { ProjectMeta } from "../types";

interface ProjectToolbarSettings {
  activeProject?: ProjectMeta;
  archiveSubmitting?: boolean;
  onRenameProject: (displayName: string) => Promise<void> | void;
  onArchiveProject: () => Promise<void> | void;
}

interface ProjectToolbarProps {
  isActive: boolean;
  mountNode: HTMLElement | null;
  projectName: string;
  phaseLabel: string;
  updatedLabel: string;
  activeProjects: ProjectMeta[];
  activeProjectId?: string;
  currentPhase?: string;
  settings?: ProjectToolbarSettings;
  onSelectProject: (projectId: string) => Promise<void> | void;
  onCreateProject: (title: string) => Promise<boolean | void> | boolean | void;
  onOpenGithub?: () => void;
  onOpenAigc?: () => void;
  onOpenCopywriting?: () => void;
  onOpenGameModel?: () => void;
  onOpenSkills?: () => void;
  onOpenMcp?: (tool: McpTool) => void;
}

export function ProjectToolbar(props: ProjectToolbarProps) {
  const {
    isActive,
    mountNode,
    projectName,
    phaseLabel,
    updatedLabel,
    activeProjects,
    activeProjectId,
    currentPhase,
    settings,
    onSelectProject,
    onCreateProject,
    onOpenGithub,
    onOpenAigc,
    onOpenCopywriting,
    onOpenGameModel,
    onOpenSkills,
    onOpenMcp,
  } = props;

  const [projectPanelOpen, setProjectPanelOpen] = useState(false);
  const [projectCreateMode, setProjectCreateMode] = useState(false);
  const [projectTitleDraft, setProjectTitleDraft] = useState("");
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [renameDraft, setRenameDraft] = useState("");
  const projectPanelRef = useRef<HTMLDivElement>(null);
  const projectPanelButtonRef = useRef<HTMLButtonElement>(null);
  const settingsPanelRef = useRef<HTMLDivElement>(null);
  const settingsButtonRef = useRef<HTMLButtonElement>(null);

  const closeProjectPanel = () => {
    setProjectPanelOpen(false);
    setProjectCreateMode(false);
    setProjectTitleDraft("");
  };

  const closeSettingsPanel = () => {
    setSettingsOpen(false);
    setRenameDraft("");
  };

  useEffect(() => {
    if (!projectPanelOpen && !settingsOpen) {
      return;
    }

    const handlePointerDown = (event: MouseEvent) => {
      const target = event.target as Node | null;
      if (
        projectPanelRef.current?.contains(target) ||
        projectPanelButtonRef.current?.contains(target) ||
        settingsPanelRef.current?.contains(target) ||
        settingsButtonRef.current?.contains(target)
      ) {
        return;
      }
      closeProjectPanel();
      closeSettingsPanel();
    };

    document.addEventListener("mousedown", handlePointerDown);
    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
    };
  }, [projectPanelOpen, settingsOpen]);

  if (!isActive || !mountNode) {
    return null;
  }

  const handleCreateProject = async () => {
    const title = projectTitleDraft.trim();
    if (!title) {
      return;
    }
    const result = await onCreateProject(title);
    if (result !== false) {
      closeProjectPanel();
    }
  };

  const handleRenameProject = async () => {
    const displayName = renameDraft.trim();
    if (!displayName || !settings) {
      return;
    }
    await settings.onRenameProject(displayName);
    closeSettingsPanel();
  };

  const toolbar = (
    <div className="project-toolbar">
      <div className="project-toolbar-info">
        <div className="project-toolbar-meta">
          <span className="project-toolbar-label">项目名</span>
          <strong>{projectName}</strong>
        </div>
        <div className="project-toolbar-meta">
          <span className="project-toolbar-label">项目阶段</span>
          <strong>{phaseLabel}</strong>
        </div>
        <div className="project-toolbar-meta">
          <span className="project-toolbar-label">更新时间</span>
          <strong>{updatedLabel}</strong>
        </div>
      </div>

      <div className="project-toolbar-menu">
        {onOpenSkills ? (
          <button
            type="button"
            className="project-toolbar-settings project-toolbar-skills-btn"
            onClick={() => {
              closeProjectPanel();
              closeSettingsPanel();
              onOpenSkills();
            }}
            title="Skills 能力"
          >
            <svg
              viewBox="0 0 24 24"
              width="16"
              height="16"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M8.8 3.8h3.1a2.1 2.1 0 1 0 4.2 0h2.1a2 2 0 0 1 2 2v4.1h-2a2.1 2.1 0 1 0 0 4.2h2v4.1a2 2 0 0 1-2 2h-4.1v-2a2.1 2.1 0 1 0-4.2 0v2H5.8a2 2 0 0 1-2-2v-3.1a2.1 2.1 0 1 0 0-4.2V5.8a2 2 0 0 1 2-2h3z" />
            </svg>
          </button>
        ) : null}

        {onOpenMcp ? (
          <>
            {([
              { tool: "unity" as McpTool, title: "Unity MCP" },
              { tool: "godot" as McpTool, title: "Godot MCP" },
              { tool: "ue" as McpTool, title: "Unreal Engine MCP" },
              { tool: "blender" as McpTool, title: "Blender MCP" },
            ]).map(({ tool, title }) => {
              const Icon = MCP_ICONS[tool];
              return (
                <button
                  key={tool}
                  type="button"
                  className="project-toolbar-settings project-toolbar-mcp-btn"
                  onClick={() => {
                    closeProjectPanel();
                    closeSettingsPanel();
                    onOpenMcp(tool);
                  }}
                  title={title}
                >
                  <Icon size={15} />
                </button>
              );
            })}
          </>
        ) : null}

        {onOpenGameModel ? (
          <button
            type="button"
            className="project-toolbar-settings"
            onClick={() => {
              closeProjectPanel();
              closeSettingsPanel();
              onOpenGameModel();
            }}
            title="游戏内模型接入"
          >
            {/* Phosphor Icons: cpu-fill */}
            <svg viewBox="0 0 256 256" width="15" height="15" fill="currentColor">
              <path d="M104,104h48v48H104Zm136,48a8,8,0,0,1-8,8H216v40a16,16,0,0,1-16,16H160v16a8,8,0,0,1-16,0V216H112v16a8,8,0,0,1-16,0V216H56a16,16,0,0,1-16-16V160H24a8,8,0,0,1,0-16H40V112H24a8,8,0,0,1,0-16H40V56A16,16,0,0,1,56,40H96V24a8,8,0,0,1,16,0V40h32V24a8,8,0,0,1,16,0V40h40a16,16,0,0,1,16,16V96h16a8,8,0,0,1,0,16H216v32h16A8,8,0,0,1,240,152ZM168,96a8,8,0,0,0-8-8H96a8,8,0,0,0-8,8v64a8,8,0,0,0,8,8h64a8,8,0,0,0,8-8Z" />
            </svg>
          </button>
        ) : null}

        {onOpenAigc ? (
          <button
            type="button"
            className="project-toolbar-settings"
            onClick={() => {
              closeProjectPanel();
              closeSettingsPanel();
              onOpenAigc();
            }}
            title="AIGC 宇宙"
          >
            {/* Phosphor Icons: magic-wand-fill */}
            <svg viewBox="0 0 256 256" width="15" height="15" fill="currentColor">
              <path d="M248,152a8,8,0,0,1-8,8H224v16a8,8,0,0,1-16,0V160H192a8,8,0,0,1,0-16h16V128a8,8,0,0,1,16,0v16h16A8,8,0,0,1,248,152ZM56,72H72V88a8,8,0,0,0,16,0V72h16a8,8,0,0,0,0-16H88V40a8,8,0,0,0-16,0V56H56a8,8,0,0,0,0,16ZM184,192h-8v-8a8,8,0,0,0-16,0v8h-8a8,8,0,0,0,0,16h8v8a8,8,0,0,0,16,0v-8h8a8,8,0,0,0,0-16ZM219.31,80,80,219.31a16,16,0,0,1-22.62,0L36.68,198.63a16,16,0,0,1,0-22.63L176,36.69a16,16,0,0,1,22.63,0l20.68,20.68A16,16,0,0,1,219.31,80ZM208,68.69,187.31,48l-32,32L176,100.69Z" />
            </svg>
          </button>
        ) : null}

        {onOpenCopywriting ? (
          <button
            type="button"
            className="project-toolbar-settings"
            onClick={() => {
              closeProjectPanel();
              closeSettingsPanel();
              onOpenCopywriting();
            }}
            title="文案加工台"
          >
            <svg viewBox="0 0 256 256" width="15" height="15" fill="currentColor">
              <path d="M227.31,73.37,182.63,28.68a16,16,0,0,0-22.63,0L36.69,152A15.86,15.86,0,0,0,32,163.31V208a16,16,0,0,0,16,16H92.69A15.86,15.86,0,0,0,104,219.31L227.31,96A16,16,0,0,0,227.31,73.37ZM92.69,208H48V163.31l88-88L180.69,120ZM192,108.69,147.31,64,171.31,40,216,84.69ZM232,216a8,8,0,0,1-8,8H136a8,8,0,0,1,0-16h88A8,8,0,0,1,232,216Z" />
            </svg>
          </button>
        ) : null}

        {onOpenGithub ? (
          <button
            type="button"
            className="project-toolbar-github"
            onClick={() => {
              closeProjectPanel();
              closeSettingsPanel();
              onOpenGithub();
            }}
            title="GitHub 可视化"
          >
            <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
              <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z"/>
            </svg>
          </button>
        ) : null}

        <button
          ref={projectPanelButtonRef}
          type="button"
          className={`project-toolbar-toggle${projectPanelOpen ? " is-active" : ""}`}
          onClick={() => {
            if (projectPanelOpen) {
              closeProjectPanel();
              return;
            }
            closeSettingsPanel();
            setProjectPanelOpen(true);
          }}
        >
          项目选单
        </button>

        {settings ? (
          <button
            ref={settingsButtonRef}
            type="button"
            className={`project-toolbar-settings${settingsOpen ? " is-active" : ""}`}
            onClick={() => {
              if (settingsOpen) {
                closeSettingsPanel();
                return;
              }
              closeProjectPanel();
              setRenameDraft(
                settings.activeProject?.display_name ||
                  settings.activeProject?.title ||
                  "",
              );
              setSettingsOpen(true);
            }}
            title="项目设置"
          >
            ⚙
          </button>
        ) : null}

        {settingsOpen && settings ? (
          <div
            ref={settingsPanelRef}
            className="project-toolbar-panel project-toolbar-settings-panel"
          >
            <div className="project-toolbar-panel-title">项目设置</div>

            <div className="project-toolbar-settings-section">
              <div className="project-toolbar-settings-label">重命名项目</div>
              <div className="project-toolbar-settings-row">
                <input
                  className="project-toolbar-settings-input"
                  type="text"
                  value={renameDraft}
                  onChange={(event) => setRenameDraft(event.target.value)}
                  placeholder="输入新名称"
                  onKeyDown={(event) => {
                    if (event.key === "Enter" && renameDraft.trim()) {
                      void handleRenameProject();
                    }
                  }}
                />
                <button
                  type="button"
                  className="shell-btn primary compact"
                  disabled={
                    !renameDraft.trim() ||
                    renameDraft ===
                      (settings.activeProject?.display_name ||
                        settings.activeProject?.title)
                  }
                  onClick={() => {
                    void handleRenameProject();
                  }}
                >
                  确认
                </button>
              </div>
            </div>

            {!settings.activeProject?.archived ? (
              <div className="project-toolbar-settings-section">
                <div className="project-toolbar-settings-label">归档项目</div>
                <button
                  type="button"
                  className="shell-btn danger compact"
                  disabled={settings.archiveSubmitting}
                  onClick={() => {
                    void settings.onArchiveProject();
                  }}
                >
                  {settings.archiveSubmitting ? "归档中..." : "归档当前项目"}
                </button>
              </div>
            ) : null}
          </div>
        ) : null}

        {projectPanelOpen ? (
          <div ref={projectPanelRef} className="project-toolbar-panel">
            {!projectCreateMode ? (
              <>
                <div className="project-toolbar-panel-title">切换项目</div>
                <div className="project-toolbar-list">
                  {activeProjects.map((project) => {
                    const phase =
                      project.id === activeProjectId
                        ? currentPhase || project.last_phase || ""
                        : project.last_phase || "";
                    return (
                      <button
                        key={project.id}
                        type="button"
                        className={`project-toolbar-item${
                          project.id === activeProjectId ? " is-active" : ""
                        }`}
                        onClick={() => {
                          void onSelectProject(project.id);
                          closeProjectPanel();
                        }}
                      >
                        <div className="project-toolbar-item-head">
                          <strong className="project-toolbar-item-name">
                            {project.display_name || project.id}
                          </strong>
                          <div className="project-toolbar-item-meta-row">
                            <span className="project-toolbar-item-sub">
                              {PHASE_LABEL[phase] || phase || "暂无阶段"}
                            </span>
                            <span className="project-toolbar-item-sub">
                              {projectUpdated(project)}
                            </span>
                          </div>
                          {project.id === activeProjectId ? (
                            <span className="tag active">当前</span>
                          ) : null}
                        </div>
                      </button>
                    );
                  })}
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
                  onKeyDown={(event) => {
                    if (event.key === "Enter") {
                      void handleCreateProject();
                    }
                  }}
                />
                <div className="project-toolbar-create-actions">
                  <button
                    type="button"
                    className="shell-btn primary"
                    onClick={() => {
                      void handleCreateProject();
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
    </div>
  );

  return createPortal(toolbar, mountNode);
}
