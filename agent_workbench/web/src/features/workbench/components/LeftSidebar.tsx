import { useState } from "react";

import { projectUpdated } from "../utils";
import type { ProjectMeta, ViewState, WorkspaceFileItem } from "../types";

interface LeftSidebarProps {
  sidebarMode: "projects" | "project";
  projectName: string;
  activeProjectId: string;
  projects: ProjectMeta[];
  files: WorkspaceFileItem[];
  currentView: ViewState;
  onBack: () => void;
  onRefresh: () => void;
  onReset: () => void;
  onOpenProject: (projectId: string) => void;
  onOpenFile: (fileId: string) => void;
  onCreateProject: (projectId: string, title: string) => Promise<boolean>;
}

export function LeftSidebar(props: LeftSidebarProps) {
  const {
    sidebarMode,
    projectName,
    activeProjectId,
    projects,
    files,
    currentView,
    onBack,
    onRefresh,
    onReset,
    onOpenProject,
    onOpenFile,
    onCreateProject,
  } = props;

  const [projectIdInput, setProjectIdInput] = useState("");
  const [projectTitleInput, setProjectTitleInput] = useState("");

  const inProject = sidebarMode === "project";

  const handleCreate = async () => {
    const ok = await onCreateProject(projectIdInput.trim(), projectTitleInput.trim());
    if (!ok) {
      return;
    }
    setProjectIdInput("");
    setProjectTitleInput("");
  };

  return (
    <aside className="shell left">
      <div className="head">
        <div className="head-row">
          <strong>{inProject ? projectName : "Workspace"}</strong>
          <button
            className="shell-btn compact"
            type="button"
            onClick={onBack}
            style={{ display: inProject ? "inline-flex" : "none" }}
          >
            Back
          </button>
        </div>
      </div>

      {!inProject ? (
        <div>
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
          <section className="section">
            <span className="section-title">Projects</span>
            <div className="list">
              {!projects.length ? (
                <div className="empty">No projects yet.</div>
              ) : (
                projects.map((project) => {
                  const tag =
                    project.id === activeProjectId
                      ? "ACTIVE"
                      : project.archived
                        ? "ARCHIVED"
                        : "OPEN";
                  return (
                    <button
                      key={project.id}
                      type="button"
                      className={"item" + (project.id === activeProjectId ? " active" : "")}
                      onClick={() => onOpenProject(project.id)}
                    >
                      <div className="item-title">
                        <span>{project.display_name || project.id}</span>
                        <span className={"tag " + (tag === "ACTIVE" ? "active" : "")}>{tag}</span>
                      </div>
                      <div className="item-sub">
                        {project.id} · {project.last_phase || "No phase yet"}
                      </div>
                      <div className="item-sub">{projectUpdated(project)}</div>
                      <div className="item-sub preview">
                        {project.last_message_preview || "No assistant message yet"}
                      </div>
                    </button>
                  );
                })
              )}
            </div>
          </section>
        </div>
      ) : (
        <div>
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
    </aside>
  );
}
