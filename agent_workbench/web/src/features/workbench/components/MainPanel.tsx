import {
  Suspense,
  lazy,
  useEffect,
  useState,
  type ReactNode,
  type RefObject,
} from "react";

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
import { AgentMessages } from "./mainPanel/AgentMessages";
import { Composer } from "./mainPanel/Composer";
import { FileView } from "./mainPanel/FileView";

const GithubPage = lazy(() =>
  import("../../github/components/GithubPage").then((module) => ({
    default: module.GithubPage,
  })),
);
const AigcPage = lazy(() =>
  import("../../aigc/components/AigcPage").then((module) => ({
    default: module.AigcPage,
  })),
);
const CopywritingPage = lazy(() =>
  import("../../copywriting/components/CopywritingPage").then((module) => ({
    default: module.CopywritingPage,
  })),
);
const GameModelPage = lazy(() =>
  import("../../game-model/components/GameModelPage").then((module) => ({
    default: module.GameModelPage,
  })),
);
const McpPage = lazy(() =>
  import("../../mcp/components/McpPage").then((module) => ({
    default: module.McpPage,
  })),
);
const SkillsWorkbenchPage = lazy(() =>
  import("../../skills/components/SkillsWorkbenchPage").then((module) => ({
    default: module.SkillsWorkbenchPage,
  })),
);

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
  onUploadFileAsset: (
    fileId: string,
    name: string,
    dataUrl: string,
  ) => Promise<{ markdown: string }>;
}

function LazyPersistentView({
  active,
  children,
}: {
  active: boolean;
  children: ReactNode;
}) {
  const [shouldMount, setShouldMount] = useState(active);

  useEffect(() => {
    if (active) {
      setShouldMount(true);
    }
  }, [active]);

  if (!shouldMount) {
    return null;
  }

  return (
    <div className="persistent-view" hidden={!active}>
      <Suspense fallback={<div className="empty">加载中...</div>}>
        {children}
      </Suspense>
    </div>
  );
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
    onUploadFileAsset,
  } = props;

  const isSpecialView =
    currentView.type === "github" ||
    currentView.type === "aigc" ||
    currentView.type === "copywriting" ||
    currentView.type === "game-model" ||
    currentView.type === "skills" ||
    currentView.type === "mcp";

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
        <div className="special-view-container" hidden={!isSpecialView}>
          <LazyPersistentView active={currentView.type === "github"}>
            <GithubPage />
          </LazyPersistentView>
          <LazyPersistentView active={currentView.type === "aigc"}>
            <AigcPage />
          </LazyPersistentView>
          <LazyPersistentView active={currentView.type === "copywriting"}>
            <CopywritingPage key={currentProjectId} />
          </LazyPersistentView>
          <LazyPersistentView active={currentView.type === "game-model"}>
            <GameModelPage key={currentProjectId} />
          </LazyPersistentView>
          <LazyPersistentView active={currentView.type === "skills"}>
            <SkillsWorkbenchPage key={currentProjectId} projectId={currentProjectId} />
          </LazyPersistentView>
          <LazyPersistentView
            active={currentView.type === "mcp" && currentView.tool === "unity"}
          >
            <McpPage key={`${currentProjectId}::unity`} tool="unity" />
          </LazyPersistentView>
          <LazyPersistentView
            active={currentView.type === "mcp" && currentView.tool === "godot"}
          >
            <McpPage key={`${currentProjectId}::godot`} tool="godot" />
          </LazyPersistentView>
          <LazyPersistentView
            active={currentView.type === "mcp" && currentView.tool === "blender"}
          >
            <McpPage key={`${currentProjectId}::blender`} tool="blender" />
          </LazyPersistentView>
          <LazyPersistentView active={currentView.type === "mcp" && currentView.tool === "ue"}>
            <McpPage key={`${currentProjectId}::ue`} tool="ue" />
          </LazyPersistentView>
        </div>

        <div className="persistent-view" hidden={isSpecialView || currentView.type !== "agent"}>
          <AgentMessages
            agentKey={currentView.type === "agent" ? currentView.id : currentAgent}
            currentAgent={currentAgent}
            readOnly={readOnly}
            requestInFlight={requestInFlight}
            historyByAgent={historyByAgent}
            transientChat={transientChat}
            actions={actions}
            onAction={onAction}
          />
        </div>

        <div className="persistent-view" hidden={isSpecialView || currentView.type !== "file"}>
          <FileView
            currentView={currentView}
            currentProjectId={currentProjectId}
            fileItems={fileItems}
            fileCache={fileCache}
            fileEditable={fileEditable}
            onSaveFile={onSaveFile}
            onUploadFileAsset={onUploadFileAsset}
          />
        </div>
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
