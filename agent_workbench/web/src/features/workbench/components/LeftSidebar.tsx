import { useRef, useState, type MouseEvent } from "react";

import { projectUpdated } from "../utils";
import type { ProjectMeta, ViewState, WorkspaceFileItem } from "../types";

interface LeftSidebarProps {
  sidebarMode: "projects" | "project" | "history";
  projectName: string;
  activeProjectId: string;
  projects: ProjectMeta[];
  archivedProjects: ProjectMeta[];
  files: WorkspaceFileItem[];
  currentView: ViewState;
  onBack: () => void;
  onOpenHistory: () => void;
  onRefresh: () => void;
  onReset: () => void;
  onOpenProject: (projectId: string) => void;
  onOpenFile: (fileId: string) => void;
  onCreateProject: (projectId: string, title: string) => Promise<boolean>;
  onRenameProject: (projectId: string, displayName: string) => void;
  onArchiveProject: (projectId: string) => void;
  onRestoreProject: (projectId: string) => void;
  onDeleteProject: (projectId: string) => void;
}

export function LeftSidebar(props: LeftSidebarProps) {
  const {
    sidebarMode,
    projectName,
    activeProjectId,
    projects,
    archivedProjects,
    files,
    currentView,
    onBack,
    onOpenHistory,
    onRefresh,
    onReset,
    onOpenProject,
    onOpenFile,
    onCreateProject,
    onRenameProject,
    onArchiveProject,
    onRestoreProject,
    onDeleteProject,
  } = props;

  const [projectIdInput, setProjectIdInput] = useState("");
  const [projectTitleInput, setProjectTitleInput] = useState("");
  const [menuProjectId, setMenuProjectId] = useState("");
  const [menuTop, setMenuTop] = useState(0);
  const [renameDraft, setRenameDraft] = useState("");
  const shellRef = useRef<HTMLElement | null>(null);

  const inProject = sidebarMode === "project";
  const inHistory = sidebarMode === "history";
  const selectedProject =
    !inProject && !inHistory
      ? projects.find((project) => project.id === menuProjectId) || null
      : null;

  const handleCreate = async () => {
    const ok = await onCreateProject(projectIdInput.trim(), projectTitleInput.trim());
    if (!ok) {
      return;
    }
    setProjectIdInput("");
    setProjectTitleInput("");
  };

  const toggleProjectMenu = (event: MouseEvent<HTMLButtonElement>, project: ProjectMeta) => {
    if (menuProjectId === project.id) {
      setMenuProjectId("");
      setMenuTop(0);
      setRenameDraft("");
      return;
    }

    const shellRect = shellRef.current?.getBoundingClientRect();
    const buttonRect = event.currentTarget.getBoundingClientRect();
    setMenuProjectId(project.id);
    setMenuTop(shellRect ? buttonRect.top - shellRect.top - 6 : 0);
    setRenameDraft(project.display_name || project.id);
  };

  return (
    <aside className="shell left" ref={shellRef}>
      <div className="head">
        <div className="head-row">
          <strong>{inProject ? projectName : inHistory ? "历史项目" : "工作区"}</strong>
          <button
            className="shell-btn compact"
            type="button"
            onClick={onBack}
            style={{ display: inProject || inHistory ? "inline-flex" : "none" }}
          >
            返回
          </button>
        </div>
      </div>

      {!inProject && !inHistory ? (
        <div className="sidebar-pane">
          <div className="create-box">
            <input
              value={projectIdInput}
              onChange={(event) => setProjectIdInput(event.target.value)}
              type="text"
              placeholder="项目 ID，例如 arcade-run"
            />
            <input
              value={projectTitleInput}
              onChange={(event) => setProjectTitleInput(event.target.value)}
              type="text"
              placeholder="项目显示名，可选"
            />
            <div className="row">
              <button
                className="shell-btn primary"
                type="button"
                onClick={() => {
                  void handleCreate();
                }}
              >
                新建项目
              </button>
              <button className="shell-btn" type="button" onClick={onRefresh}>
                刷新
              </button>
            </div>
          </div>

          <section className="section section-fill">
            <span className="section-title">项目列表</span>
            <div className="list">
              {!projects.length ? (
                <div className="empty">还没有项目。</div>
              ) : (
                projects.map((project) => (
                  <div key={project.id} className="project-card-shell">
                    <button
                      type="button"
                      className={
                        "item project-card" +
                        (project.id === activeProjectId ? " active" : "")
                      }
                      onClick={() => onOpenProject(project.id)}
                    >
                      <div className="item-title">
                        <span>{project.display_name || project.id}</span>
                        <span
                          className={
                            "tag " + (project.id === activeProjectId ? "active" : "")
                          }
                        >
                          {project.id === activeProjectId ? "当前" : "打开"}
                        </span>
                      </div>
                      <div className="item-sub">
                        {project.id} · {project.last_phase || "暂无阶段"}
                      </div>
                      <div className="item-sub">{projectUpdated(project)}</div>
                      <div className="item-sub preview">
                        {project.last_message_preview || "暂无 Agent 回复"}
                      </div>
                    </button>

                    <button
                      type="button"
                      className="card-corner-btn"
                      onClick={(event) => {
                        event.stopPropagation();
                        toggleProjectMenu(event, project);
                      }}
                      aria-label={`打开 ${project.display_name || project.id} 的设置菜单`}
                    >
                      ⚙
                    </button>
                  </div>
                ))
              )}
            </div>
          </section>

          <div className="history-entry-wrap">
            <button className="history-entry" type="button" onClick={onOpenHistory}>
              <span>历史项目</span>
              <span className="tag">{archivedProjects.length}</span>
            </button>
          </div>
        </div>
      ) : inHistory ? (
        <div className="sidebar-pane">
          <section className="section section-fill">
            <span className="section-title">已归档</span>
            <div className="list">
              {!archivedProjects.length ? (
                <div className="empty">还没有历史项目。</div>
              ) : (
                archivedProjects.map((project) => (
                  <div key={project.id} className="item history-card">
                    <div className="item-title">
                      <span>{project.display_name || project.id}</span>
                      <span className="tag">已归档</span>
                    </div>
                    <div className="item-sub">
                      {project.id} · {project.last_phase || "暂无阶段"}
                    </div>
                    <div className="item-sub">{projectUpdated(project)}</div>
                    <div className="item-sub preview">
                      {project.last_message_preview || "暂无 Agent 回复"}
                    </div>
                    <div className="history-actions">
                      <button
                        className="shell-btn compact"
                        type="button"
                        onClick={() => onRestoreProject(project.id)}
                      >
                        恢复
                      </button>
                      <button
                        className="shell-btn danger compact"
                        type="button"
                        onClick={() => onDeleteProject(project.id)}
                      >
                        删除
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>
          </section>
        </div>
      ) : (
        <div className="sidebar-pane">
          <section className="section section-fill">
            <span className="section-title">工件</span>
            <div className="list">
              {files.map((file) => (
                <button
                  key={file.id}
                  type="button"
                  className={
                    "item" +
                    (currentView.type === "file" && currentView.id === file.id ? " active" : "")
                  }
                  onClick={() => onOpenFile(file.id)}
                >
                  <div className="item-title">
                    <span>{file.name}</span>
                    <span className="tag">文件</span>
                  </div>
                  <div className="item-sub">当前项目内的工件</div>
                </button>
              ))}
            </div>
          </section>
        </div>
      )}

      <div className="foot">
        <button
          className="reset-btn"
          type="button"
          onClick={onReset}
          style={{ display: inProject ? "inline-flex" : "none" }}
        >
          重置
        </button>
      </div>

      {selectedProject ? (
        <div className="sidebar-popover" style={{ top: `${menuTop}px` }}>
          <div className="menu-head">
            <label className="menu-label" htmlFor={`rename-${selectedProject.id}`}>
              重命名
            </label>
            <button
              className="menu-close-btn"
              type="button"
              onClick={() => {
                setMenuProjectId("");
                setMenuTop(0);
                setRenameDraft("");
              }}
              aria-label={`关闭 ${selectedProject.display_name || selectedProject.id} 的设置菜单`}
            >
              ×
            </button>
          </div>
          <input
            id={`rename-${selectedProject.id}`}
            value={renameDraft}
            onChange={(event) => setRenameDraft(event.target.value)}
            type="text"
            placeholder="输入显示名称"
          />
          <div className="menu-actions">
            <button
              className="shell-btn compact"
              type="button"
              onClick={() => {
                const nextName = renameDraft.trim();
                if (!nextName) {
                  return;
                }
                onRenameProject(selectedProject.id, nextName);
                setMenuProjectId("");
                setMenuTop(0);
                setRenameDraft("");
              }}
            >
              保存
            </button>
            <button
              className="shell-btn danger compact"
              type="button"
              onClick={() => {
                onArchiveProject(selectedProject.id);
                setMenuProjectId("");
                setMenuTop(0);
                setRenameDraft("");
              }}
            >
              归档
            </button>
          </div>
        </div>
      ) : null}
    </aside>
  );
}
