import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

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
