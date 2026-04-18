import type { ViewState, WorkspaceFileItem } from "../types";

interface LeftSidebarProps {
  files: WorkspaceFileItem[];
  currentView: ViewState;
  onOpenFile: (fileId: string) => void;
}

export function LeftSidebar(props: LeftSidebarProps) {
  const { files, currentView, onOpenFile } = props;

  return (
    <aside className="shell left workbench-left">
      <div className="head">
        <div className="head-row">
          <strong>项目工件</strong>
        </div>
      </div>

      <div className="sidebar-pane">
        <section className="section section-fill">
          <span className="section-title">当前项目文件</span>
          <div className="list">
            {!files.length ? (
              <div className="empty">当前项目还没有可查看的工件。</div>
            ) : (
              files.map((file) => (
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
                    <span className="tag">工件</span>
                  </div>
                  <div className="item-sub">当前项目内的正式工件文件</div>
                </button>
              ))
            )}
          </div>
        </section>
      </div>
    </aside>
  );
}
