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
    !inProject && !inHistory ? projects.find((project) => project.id === menuProjectId) || null : null;

  const handleCreate = async () => {
    const ok = await onCreateProject(projectIdInput.trim(), projectTitleInput.trim());
    if (!ok) {
      return;
    }
    setProjectIdInput("");
    setProjectTitleInput("");
  };

  const toggleProjectMenu = (
    event: MouseEvent<HTMLButtonElement>,
    project: ProjectMeta,
  ) => {
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
          <strong>{inProject ? projectName : inHistory ? "History Projects" : "Workspace"}</strong>
          <button
            className="shell-btn compact"
            type="button"
            onClick={onBack}
            style={{ display: inProject || inHistory ? "inline-flex" : "none" }}
          >
            Back
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
              placeholder="project id, e.g. arcade-run"
            />
            <input
              value={projectTitleInput}
              onChange={(event) => setProjectTitleInput(event.target.value)}
              type="text"
              placeholder="display name, optional"
            />
            <div className="row">
              <button
                className="shell-btn primary"
                type="button"
                onClick={() => {
                  void handleCreate();
                }}
              >
                New Project
              </button>
              <button className="shell-btn" type="button" onClick={onRefresh}>
                Refresh
              </button>
            </div>
          </div>

          <section className="section section-fill">
            <span className="section-title">Projects</span>
            <div className="list">
              {!projects.length ? (
                <div className="empty">No projects yet.</div>
              ) : (
                projects.map((project) => (
                  <div key={project.id} className="project-card-shell">
                    <button
                      type="button"
                      className={"item project-card" + (project.id === activeProjectId ? " active" : "")}
                      onClick={() => onOpenProject(project.id)}
                    >
                      <div className="item-title">
                        <span>{project.display_name || project.id}</span>
                        <span className={"tag " + (project.id === activeProjectId ? "active" : "")}>
                          {project.id === activeProjectId ? "ACTIVE" : "OPEN"}
                        </span>
                      </div>
                      <div className="item-sub">
                        {project.id} 路 {project.last_phase || "No phase yet"}
                      </div>
                      <div className="item-sub">{projectUpdated(project)}</div>
                      <div className="item-sub preview">
                        {project.last_message_preview || "No assistant message yet"}
                      </div>
                    </button>

                      <button
                        type="button"
                        className="card-corner-btn"
                        onClick={(event) => {
                          event.stopPropagation();
                          toggleProjectMenu(event, project);
                        }}
                        aria-label={`Open settings for ${project.display_name || project.id}`}
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
              <span>History Projects</span>
              <span className="tag">{archivedProjects.length}</span>
            </button>
          </div>
        </div>
      ) : inHistory ? (
        <div className="sidebar-pane">
          <section className="section section-fill">
            <span className="section-title">Archived</span>
            <div className="list">
              {!archivedProjects.length ? (
                <div className="empty">No archived projects yet.</div>
              ) : (
                archivedProjects.map((project) => (
                  <div key={project.id} className="item history-card">
                    <div className="item-title">
                      <span>{project.display_name || project.id}</span>
                      <span className="tag">ARCHIVED</span>
                    </div>
                    <div className="item-sub">
                      {project.id} 路 {project.last_phase || "No phase yet"}
                    </div>
                    <div className="item-sub">{projectUpdated(project)}</div>
                    <div className="item-sub preview">
                      {project.last_message_preview || "No assistant message yet"}
                    </div>
                    <div className="history-actions">
                      <button
                        className="shell-btn compact"
                        type="button"
                        onClick={() => onRestoreProject(project.id)}
                      >
                        Restore
                      </button>
                      <button
                        className="shell-btn danger compact"
                        type="button"
                        onClick={() => onDeleteProject(project.id)}
                      >
                        Delete
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
            <span className="section-title">Artifacts</span>
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
                    <span className="tag">FILE</span>
                  </div>
                  <div className="item-sub">Project-local artifact</div>
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
          Reset
        </button>
      </div>

      {selectedProject ? (
        <div className="sidebar-popover" style={{ top: `${menuTop}px` }}>
          <div className="menu-head">
            <label className="menu-label" htmlFor={`rename-${selectedProject.id}`}>
              Rename
            </label>
            <button
              className="menu-close-btn"
              type="button"
              onClick={() => {
                setMenuProjectId("");
                setMenuTop(0);
                setRenameDraft("");
              }}
              aria-label={`Close settings for ${selectedProject.display_name || selectedProject.id}`}
            >
              ×
            </button>
          </div>
          <input
            id={`rename-${selectedProject.id}`}
            value={renameDraft}
            onChange={(event) => setRenameDraft(event.target.value)}
            type="text"
            placeholder="Display name"
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
              Save
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
              Archive
            </button>
          </div>
        </div>
      ) : null}
    </aside>
  );
}
