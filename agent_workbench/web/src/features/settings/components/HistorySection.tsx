import type { ProjectMeta } from "../../workbench/types";

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
