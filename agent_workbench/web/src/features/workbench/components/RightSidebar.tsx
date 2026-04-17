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
        <strong>项目状态</strong>
      </div>
      <div className="status-box">
        <div className="status-card">
          <div className="status-grid">
            <div>
              <div className="status-label">项目</div>
              <div className="status-value">{projectName}</div>
            </div>
            <div>
              <div className="status-label">Agent</div>
              <div className="status-value">{agentName(currentAgent)}</div>
            </div>
            <div>
              <div className="status-label">阶段</div>
              <div className="status-value">{phaseLabel}</div>
            </div>
            <div>
              <div className="status-label">迭代次数</div>
              <div className="status-value">{iterationCount}</div>
            </div>
            <div>
              <div className="status-label">工件</div>
              <div className="status-value">{filesCount} 个文件</div>
            </div>
            <div>
              <div className="status-label">模式</div>
              <div className="status-value">{modeLabel}</div>
            </div>
            <div>
              <div className="status-label">更新时间</div>
              <div className="status-value">{statusUpdated}</div>
            </div>
            <div>
              <div className="status-label">上个阶段</div>
              <div className="status-value">{statusLastPhase}</div>
            </div>
          </div>
        </div>
      </div>

      <section className="section">
        <span className="section-title">Agent 列表</span>
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
                <span className="tag">{agent.key === currentAgent ? "当前" : "历史"}</span>
              </div>
              <div className="item-sub">
                {agent.key === currentAgent ? "当前可写会话" : "只读历史记录"}
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
