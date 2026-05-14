import type { ProjectWorkspace } from "../../workbench/types";

export const WORKSPACE_KIND_OPTIONS = [
  { value: "unity", label: "Unity" },
  { value: "generic", label: "Generic" },
  { value: "godot", label: "Godot" },
  { value: "blender", label: "Blender" },
];

function kindLabel(kind: string): string {
  if (kind === "unity") return "Unity";
  if (kind === "godot") return "Godot";
  if (kind === "blender") return "Blender";
  return "Generic";
}

function sourceLabel(source?: string): string {
  if (source === "legacy" || source === "legacy-api") return "兼容迁移";
  return "用户添加";
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
          当前项目还没有工作区。你可以在右侧添加 Generic、Unity、Godot 或 Blender 工作区。
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
    <div className="settings-detail-stack settings-detail-stack--fill">
      <article className="settings-pane-card settings-workspace-whole">
        <div className="settings-workspace-split">
          <div className="settings-workspace-left">
            <div className="settings-card-head">
              <h2 className="settings-card-title">当前工作区</h2>
              <span className="settings-chip">{workspaces.length} 项</span>
            </div>
            {workspaceList}
          </div>

          <div className="settings-workspace-right">
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
                  placeholder="例如：主游戏工程"
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
          </div>
        </div>
      </article>
    </div>
  );
}
