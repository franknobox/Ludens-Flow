import type { ChangeEvent, KeyboardEvent, RefObject } from "react";

import { agentName } from "../utils";
import type {
  AgentKey,
  HistoryByAgent,
  RenderMessage,
  TransientChat,
  ViewState,
  WorkflowAction,
  WorkspaceFileItem,
} from "../types";

interface MainPanelProps {
  currentView: ViewState;
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
  inputText: string;
  errorText: string;
  pendingImages: string[];
  contentAreaRef: RefObject<HTMLElement>;
  fileInputRef: RefObject<HTMLInputElement>;
  onInputTextChange: (value: string) => void;
  onSend: () => void;
  onInputKeyDown: (event: KeyboardEvent<HTMLTextAreaElement>) => void;
  onAttachClick: () => void;
  onImageChange: (event: ChangeEvent<HTMLInputElement>) => void;
  onRemoveImage: (index: number) => void;
  onAction: (actionId: string) => void;
}

function renderMessageRow(agentKey: AgentKey, item: RenderMessage, index: number) {
  const user = item.role === "user";
  const sender = user ? "You" : agentName(agentKey);
  const avatar = user ? "ME" : sender.slice(0, 1).toUpperCase();

  return (
    <div className={"msg " + (user ? "user" : "agent")} key={`${agentKey}-${index}-${item.role}`}>
      <div className="avatar">{avatar}</div>
      <div>
        <div className="sender">
          {sender} · {item.phase || ""}
        </div>
        {item.thinking ? (
          <div className="bubble thinking">
            <span>Thinking</span>
            <span className="thinking-dots">
              <span></span>
              <span></span>
              <span></span>
            </span>
          </div>
        ) : (
          <div className="bubble">{item.content}</div>
        )}
      </div>
    </div>
  );
}

function renderFileView(
  currentView: ViewState,
  fileItems: WorkspaceFileItem[],
  fileCache: Record<string, string>,
) {
  if (currentView.type !== "file") {
    return null;
  }

  const file = fileItems.find((item) => item.id === currentView.id);
  const content = fileCache[currentView.id];
  const showContent = typeof content === "string" ? content || "(empty)" : "Loading...";

  return (
    <div className="file-panel">
      <div className="file-title">{file?.name || currentView.id}</div>
      <pre className="file-content">{showContent}</pre>
    </div>
  );
}

export function MainPanel(props: MainPanelProps) {
  const {
    currentView,
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
    inputText,
    errorText,
    pendingImages,
    contentAreaRef,
    fileInputRef,
    onInputTextChange,
    onSend,
    onInputKeyDown,
    onAttachClick,
    onImageChange,
    onRemoveImage,
    onAction,
  } = props;

  let messageRows: RenderMessage[] = [];
  if (currentView.type === "agent") {
    messageRows = [...(historyByAgent[currentView.id] || [])];
    if (transientChat && transientChat.agentKey === currentView.id) {
      messageRows.push({
        role: "user",
        content: transientChat.userText,
        phase: transientChat.phase,
      });
      if (transientChat.thinking) {
        messageRows.push({
          role: "assistant",
          content: "",
          phase: transientChat.phase,
          thinking: true,
        });
      }
    }
  }

  const shouldRenderActions =
    currentView.type === "agent" &&
    currentView.id === currentAgent &&
    !readOnly &&
    !requestInFlight &&
    actions.length > 0;

  return (
    <main className="main">
      <header className="main-header">
        <div>
          <div className="hero-kicker">Multi-Project Workspace</div>
          <h1 className="hero-title">{title}</h1>
          <div className="hero-sub">{subtitle}</div>
        </div>
        <div className="meta">
          <span className="badge project">{projectName}</span>
          <span className="badge phase">{phaseLabel}</span>
          <span className="badge mode">{modeBadge}</span>
          {readOnly && currentView.type === "agent" ? (
            <span className="badge readonly">Read Only · {agentName(currentAgent)}</span>
          ) : null}
        </div>
      </header>

      <section className="content" ref={contentAreaRef}>
        {currentView.type === "agent" ? (
          <div className="messages">
            {messageRows.length ? (
              messageRows.map((item, index) => renderMessageRow(currentView.id, item, index))
            ) : (
              <div className="empty">
                No conversation yet for {agentName(currentView.id)} in this project.
              </div>
            )}

            {shouldRenderActions ? (
              <div className="message-actions">
                <p className="title">流程选项</p>
                <div className="row">
                  {actions.map((action) => (
                    <button
                      key={action.id}
                      type="button"
                      disabled={requestInFlight}
                      onClick={() => onAction(action.id)}
                    >
                      {action.label || action.id}
                    </button>
                  ))}
                </div>
              </div>
            ) : null}
          </div>
        ) : (
          renderFileView(currentView, fileItems, fileCache)
        )}
      </section>

      {currentView.type === "agent" ? (
        <section className="composer">
          <div className="input-row">
            <textarea
              rows={1}
              value={inputText}
              disabled={readOnly || requestInFlight}
              onChange={(event) => onInputTextChange(event.target.value)}
              onKeyDown={onInputKeyDown}
                placeholder={
                  readOnly
                    ? `Read-only history. Current active agent is ${agentName(currentAgent)}.`
                    : `Talk to ${agentName(currentView.id)} inside ${projectName}...`
                }
              />
            <input
              ref={fileInputRef}
              type="file"
              accept="image/png,image/jpeg,image/webp,image/jpg"
              multiple
              onChange={onImageChange}
            />
            <button className="btn-line" type="button" disabled={readOnly || requestInFlight} onClick={onAttachClick}>
              Image
            </button>
            <button className="btn" type="button" disabled={readOnly || requestInFlight} onClick={onSend}>
              Send
            </button>
          </div>

          <div className="attachments" style={{ display: pendingImages.length ? "flex" : "none" }}>
            <span className="attachments-label">Images:</span>
            <div className="thumbs">
              {pendingImages.map((dataUrl, index) => (
                <div className="thumb" key={`${dataUrl.slice(0, 24)}-${index}`}>
                  <img src={dataUrl} alt="" />
                  <button className="remove" type="button" onClick={() => onRemoveImage(index)}>
                    x
                  </button>
                </div>
              ))}
            </div>
          </div>

          <div className="error">{errorText || ""}</div>
        </section>
      ) : null}
    </main>
  );
}
