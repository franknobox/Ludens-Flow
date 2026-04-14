import { AGENTS } from "../constants";
import { agentName } from "../utils";
import type { AgentKey, ProjectMeta, ViewState } from "../types";

interface RightSidebarProps {
  currentView: ViewState;
  currentAgent: AgentKey;
  projectName: string;
  phaseLabel: string;
  iterationCount: number;
  filesCount: number;
  modeLabel: string;
  statusUpdated: string;
  statusLastPhase: string;
  statusNote: string;
  onSelectAgent: (agent: AgentKey) => void;
  activeProject?: ProjectMeta;
}

export function RightSidebar(props: RightSidebarProps) {
  const {
    currentView,
    currentAgent,
    projectName,
    phaseLabel,
    iterationCount,
    filesCount,
    modeLabel,
    statusUpdated,
    statusLastPhase,
    statusNote,
    onSelectAgent,
  } = props;

  return (
    <aside className="shell right">
      <div className="head">
        <strong>Project Status</strong>
      </div>
      <div className="status-box">
        <div className="status-card">
          <div className="status-grid">
            <div>
              <div className="status-label">Project</div>
              <div className="status-value">{projectName}</div>
            </div>
            <div>
              <div className="status-label">Agent</div>
              <div className="status-value">{agentName(currentAgent)}</div>
            </div>
            <div>
              <div className="status-label">Phase</div>
              <div className="status-value">{phaseLabel}</div>
            </div>
            <div>
              <div className="status-label">Iterations</div>
              <div className="status-value">{iterationCount}</div>
            </div>
            <div>
              <div className="status-label">Artifacts</div>
              <div className="status-value">{filesCount} files</div>
            </div>
            <div>
              <div className="status-label">Mode</div>
              <div className="status-value">{modeLabel}</div>
            </div>
            <div>
              <div className="status-label">Updated</div>
              <div className="status-value">{statusUpdated}</div>
            </div>
            <div>
              <div className="status-label">Last Phase</div>
              <div className="status-value">{statusLastPhase}</div>
            </div>
          </div>
        </div>
      </div>

      <section className="section">
        <span className="section-title">Agents</span>
        <div className="list">
          {AGENTS.map((agent) => (
            <button
              key={agent.key}
              type="button"
              className={
                "item" +
                (currentView.type === "agent" && currentView.id === agent.key ? " active" : "")
              }
              onClick={() => onSelectAgent(agent.key)}
            >
              <div className="item-title">
                <span>{agent.name}</span>
                <span className="tag">{agent.key === currentAgent ? "CURRENT" : "HISTORY"}</span>
              </div>
              <div className="item-sub">
                {agent.key === currentAgent ? "Writable now" : "Read-only transcript"}
              </div>
            </button>
          ))}
        </div>
      </section>

      <div className="status-box">
        <div className="status-note">{statusNote}</div>
      </div>
    </aside>
  );
}
