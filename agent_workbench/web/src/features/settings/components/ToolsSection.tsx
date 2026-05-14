import type { ToolCatalogItem } from "../../workbench/types";

interface ToolsSectionProps {
  tools: ToolCatalogItem[];
  toolsByCategory: Record<string, ToolCatalogItem[]>;
}

function kindLabel(kind: string): string {
  if (kind === "unity") return "Unity";
  if (kind === "godot") return "Godot";
  if (kind === "blender") return "Blender";
  return "Generic";
}

function toolCategoryLabel(category: string): string {
  if (category === "workspace") return "工作区";
  if (category === "unity") return "Unity";
  if (category === "research") return "检索";
  return "通用";
}

function toolStatusInfo(tool: ToolCatalogItem): { label: string; className: string } {
  if (tool.writes_files) return { label: "可写入", className: "status-writable" };
  if (tool.requires_workspace) return { label: "需工作区", className: "status-workspace" };
  return { label: "只读", className: "status-readonly" };
}

export function ToolsSection({ tools, toolsByCategory }: ToolsSectionProps) {
  return (
    <div className="settings-detail-stack tools-detail-stack">
      <section className="settings-pane-card settings-pane-card-main settings-pane-scroll-frame">
        <div className="settings-card-head">
          <h2 className="settings-card-title">工具目录</h2>
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
                            {(() => {
                              const info = toolStatusInfo(tool);
                              return (
                                <span className={`settings-chip subtle ${info.className}`}>
                                  {info.label}
                                </span>
                              );
                            })()}
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
}
