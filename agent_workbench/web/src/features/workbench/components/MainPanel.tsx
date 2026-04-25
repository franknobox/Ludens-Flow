import type { RefObject } from "react";

import { agentName } from "../utils";
import type {
  AgentKey,
  ComposerAttachment,
  HistoryByAgent,
  TransientChat,
  ViewState,
  WorkflowAction,
  WorkspaceFileItem,
} from "../types";
import { GithubPage } from "../../github/components/GithubPage";
import { AigcPage } from "../../aigc/components/AigcPage";
import { GameModelPage } from "../../game-model/components/GameModelPage";
import { McpPage } from "../../mcp/components/McpPage";
import { AgentMessages } from "./mainPanel/AgentMessages";
import { Composer } from "./mainPanel/Composer";
import { FileView } from "./mainPanel/FileView";

interface MainPanelProps {
  currentView: ViewState;
  currentProjectId: string;
  currentAgent: AgentKey;
  projectName: string;
  phaseLabel: string;
  modeBadge: string;
  readOnly: boolean;
  subtitle: string;
  title: string;
  historyByAgent: HistoryByAgent;
  transientChat: TransientChat | null;
  actions: WorkflowAction[];
  requestInFlight: boolean;
  fileItems: WorkspaceFileItem[];
  fileCache: Record<string, string>;
  fileEditable: boolean;
  errorText: string;
  warningText: string;
  contentAreaRef: RefObject<HTMLElement>;
  onSend: (message: string, attachments: ComposerAttachment[]) => Promise<void>;
  onAction: (actionId: string) => void;
  onSaveFile: (fileId: string, content: string) => Promise<void>;
}

export function MainPanel(props: MainPanelProps) {
  const {
    currentView,
    currentProjectId,
    currentAgent,
    projectName,
    phaseLabel,
    modeBadge,
    readOnly,
    subtitle,
    title,
    historyByAgent,
    transientChat,
    actions,
    requestInFlight,
    fileItems,
    fileCache,
    fileEditable,
    errorText,
    warningText,
    contentAreaRef,
    onSend,
    onAction,
    onSaveFile,
  } = props;

  const isSpecialView = currentView.type === "github" || currentView.type === "aigc" || currentView.type === "game-model" || currentView.type === "mcp";

  return (
    <main className={`main${isSpecialView ? " main-special-view" : ""}`}>
      {!isSpecialView && (
        <header className="main-header">
          <div>
            <div className="hero-kicker">多项目工作台</div>
            <h1 className="hero-title">{title}</h1>
            <div className="hero-sub">{subtitle}</div>
          </div>
          <div className="meta">
            <span className="badge project">{projectName}</span>
            <span className="badge phase">{phaseLabel}</span>
            <span className="badge mode">{modeBadge}</span>
            {readOnly && currentView.type === "agent" ? (
              <span className="badge readonly">只读 · {agentName(currentAgent)}</span>
            ) : null}
          </div>
        </header>
      )}

      <section className="content" ref={contentAreaRef}>
        {currentView.type === "github" || currentView.type === "aigc" || currentView.type === "game-model" || currentView.type === "mcp" ? (
          <div className="special-view-container">
            {currentView.type === "github" ? (
              <GithubPage />
            ) : currentView.type === "aigc" ? (
              <AigcPage />
            ) : currentView.type === "mcp" ? (
              <McpPage tool={currentView.tool} />
            ) : (
              <GameModelPage />
            )}
          </div>
        ) : currentView.type === "agent" ? (
          <AgentMessages
            agentKey={currentView.id}
            currentAgent={currentAgent}
            readOnly={readOnly}
            requestInFlight={requestInFlight}
            historyByAgent={historyByAgent}
            transientChat={transientChat}
            actions={actions}
            onAction={onAction}
          />
        ) : (
          <FileView
            currentView={currentView}
            currentProjectId={currentProjectId}
            fileItems={fileItems}
            fileCache={fileCache}
            fileEditable={fileEditable}
            onSaveFile={onSaveFile}
          />
        )}
      </section>

      {!isSpecialView && currentView.type === "agent" ? (
        <Composer
          agentKey={currentView.id}
          currentAgent={currentAgent}
          projectName={projectName}
          readOnly={readOnly}
          requestInFlight={requestInFlight}
          warningText={warningText}
          errorText={errorText}
          onSend={onSend}
        />
      ) : null}
    </main>
  );
}
