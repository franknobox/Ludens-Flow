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
  FastDevProgress,
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
  gameTags: string[];
  readOnly: boolean;
  subtitle: string;
  title: string;
  historyByAgent: HistoryByAgent;
  transientChat: TransientChat | null;
  actions: WorkflowAction[];
  requestInFlight: boolean;
  mcpMode: boolean;
  fileItems: WorkspaceFileItem[];
  fileCache: Record<string, string>;
  fastDevProgress: FastDevProgress;
  fileEditable: boolean;
  errorText: string;
  warningText: string;
  contentAreaRef: RefObject<HTMLElement>;
  onSend: (message: string, attachments: ComposerAttachment[]) => Promise<void>;
  onAction: (actionId: string) => void;
  onToggleMcpMode: (enabled: boolean) => void;
  onSaveFile: (fileId: string, content: string) => Promise<void>;
  onUploadFileAsset: (
    fileId: string,
    name: string,
    dataUrl: string,
  ) => Promise<{ markdown: string }>;
  onImportGddFastDev: (file: File) => Promise<void>;
  onCloseFastDevProgress: () => void;
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
    gameTags,
    readOnly,
    subtitle,
    title,
    historyByAgent,
    transientChat,
    actions,
    requestInFlight,
    mcpMode,
    fileItems,
    fileCache,
    fastDevProgress,
    fileEditable,
    errorText,
    warningText,
    contentAreaRef,
    onSend,
    onAction,
    onToggleMcpMode,
    onSaveFile,
    onUploadFileAsset,
    onImportGddFastDev,
    onCloseFastDevProgress,
  } = props;

  const isSpecialView =
    currentView.type === "github" ||
    currentView.type === "aigc" ||
    currentView.type === "copywriting" ||
    currentView.type === "game-model" ||
    currentView.type === "skills" ||
    currentView.type === "mcp";
  const showGddFastDevImport = currentView.type === "file" && currentView.id === "gdd";

  return (
    <main className={`main${isSpecialView ? " main-special-view" : ""}`}>
      {!isSpecialView && (
        <header className="main-header">
          <div>
            <div className="hero-kicker">多项目工作台</div>
            <h1 className="hero-title">{title}</h1>
            <div className="hero-sub">{subtitle}</div>
          </div>
          <div className="meta-stack">
            <div className="meta">
              {gameTags.slice(0, 4).map((tag) => (
                <span className="badge game-tag" key={tag}>
                  {tag}
                </span>
              ))}
              {readOnly && currentView.type === "agent" ? (
                <span className="badge readonly">只读 · {agentName(currentAgent)}</span>
              ) : null}
            </div>
            {showGddFastDevImport ? (
              <label className="gdd-fastdev-import main-header-import">
                <input
                  type="file"
                  accept=".md,.txt,.pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                  hidden
                  onChange={(event) => {
                    const file = event.currentTarget.files?.[0];
                    event.currentTarget.value = "";
                    if (file) {
                      void onImportGddFastDev(file);
                    }
                  }}
                />
                <span className="btn-line btn-file">导入 GDD</span>
                <small>进入快速开发</small>
              </label>
            ) : null}
            {currentView.type === "agent" && currentAgent === "engineering" ? (
              <button
                type="button"
                className={`mcp-mode-toggle${mcpMode ? " is-on" : ""}`}
                onClick={() => onToggleMcpMode(!mcpMode)}
                title={
                  mcpMode
                    ? "MCP 模式已开启：工程 Agent 会强制进入工具调用路径。"
                    : "MCP 模式已关闭：工程 Agent 会提示你打开后再调用外部编辑器工具。"
                }
              >
                <span className="mcp-mode-dot" />
                MCP {mcpMode ? "on" : "off"}
              </button>
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

      {fastDevProgress.open ? (
        <div className="fastdev-modal-backdrop" role="presentation">
          <div className="fastdev-modal" role="dialog" aria-modal="true">
            <div className="fastdev-modal-kicker">快速开发</div>
            <h2>
              {fastDevProgress.status === "completed"
                ? "生成完成"
                : fastDevProgress.status === "failed"
                  ? "生成失败"
                  : "正在生成"}
            </h2>
            <p>{fastDevProgress.message}</p>
            {fastDevProgress.status === "running" ? (
              <div className="fastdev-progress-bar">
                <span />
              </div>
            ) : (
              <button
                type="button"
                className="btn"
                onClick={onCloseFastDevProgress}
              >
                确定
              </button>
            )}
          </div>
        </div>
      ) : null}

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
