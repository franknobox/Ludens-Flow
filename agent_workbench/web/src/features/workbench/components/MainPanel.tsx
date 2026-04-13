import { memo, useMemo, useRef, useState } from "react";
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
  errorText: string;
  contentAreaRef: RefObject<HTMLElement>;
  onSend: (message: string, images: string[]) => Promise<void>;
  onAction: (actionId: string) => void;
}

function toDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ""));
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
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

interface AgentMessagesProps {
  agentKey: AgentKey;
  currentAgent: AgentKey;
  readOnly: boolean;
  requestInFlight: boolean;
  historyByAgent: HistoryByAgent;
  transientChat: TransientChat | null;
  actions: WorkflowAction[];
  onAction: (actionId: string) => void;
}

const AgentMessages = memo(function AgentMessages(props: AgentMessagesProps) {
  const {
    agentKey,
    currentAgent,
    readOnly,
    requestInFlight,
    historyByAgent,
    transientChat,
    actions,
    onAction,
  } = props;

  const messageRows = useMemo(() => {
    const rows: RenderMessage[] = [...(historyByAgent[agentKey] || [])];
    if (transientChat && transientChat.agentKey === agentKey) {
      rows.push({
        role: "user",
        content: transientChat.userText,
        phase: transientChat.phase,
      });
      if (transientChat.thinking) {
        rows.push({
          role: "assistant",
          content: "",
          phase: transientChat.phase,
          thinking: true,
        });
      }
    }
    return rows;
  }, [agentKey, historyByAgent, transientChat]);

  const MAX_RENDER_MESSAGES = 160;
  const hiddenCount =
    messageRows.length > MAX_RENDER_MESSAGES
      ? messageRows.length - MAX_RENDER_MESSAGES
      : 0;
  const visibleRows =
    hiddenCount > 0 ? messageRows.slice(-MAX_RENDER_MESSAGES) : messageRows;

  const shouldRenderActions =
    agentKey === currentAgent &&
    !readOnly &&
    !requestInFlight &&
    actions.length > 0;

  return (
    <div className="messages">
      {visibleRows.length ? (
        <>
          {hiddenCount > 0 ? (
            <div className="history-hint">
              已折叠较早消息 {hiddenCount} 条（仅渲染最近 {MAX_RENDER_MESSAGES} 条）。
            </div>
          ) : null}
          {visibleRows.map((item, index) => renderMessageRow(agentKey, item, index))}
        </>
      ) : (
        <div className="empty">
          No conversation yet for {agentName(agentKey)} in this project.
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
  );
});

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
    errorText,
    contentAreaRef,
    onSend,
    onAction,
  } = props;

  const [inputText, setInputText] = useState("");
  const [pendingImages, setPendingImages] = useState<string[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleSend = async () => {
    if (readOnly || requestInFlight) {
      return;
    }

    const text = inputText.trim();
    if (!text && !pendingImages.length) {
      return;
    }

    const images = pendingImages.slice();
    setPendingImages([]);
    setInputText("");
    await onSend(text, images);
  };

  const handleInputKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void handleSend();
    }
  };

  const handleImageChange = async (event: ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(event.target.files || []);
    event.target.value = "";

    const urls: string[] = [];
    for (const file of files) {
      if (!file.type.startsWith("image/")) {
        continue;
      }
      try {
        urls.push(await toDataUrl(file));
      } catch {
        // no-op
      }
    }

    if (urls.length) {
      setPendingImages((prev) => [...prev, ...urls]);
    }
  };

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
              onChange={(event) => setInputText(event.target.value)}
              onKeyDown={handleInputKeyDown}
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
              onChange={(event) => {
                void handleImageChange(event);
              }}
            />
            <button
              className="btn-line"
              type="button"
              disabled={readOnly || requestInFlight}
              onClick={() => fileInputRef.current?.click()}
            >
              Image
            </button>
            <button
              className="btn"
              type="button"
              disabled={readOnly || requestInFlight}
              onClick={() => {
                void handleSend();
              }}
            >
              Send
            </button>
          </div>

          <div className="attachments" style={{ display: pendingImages.length ? "flex" : "none" }}>
            <span className="attachments-label">Images:</span>
            <div className="thumbs">
              {pendingImages.map((dataUrl, index) => (
                <div className="thumb" key={`${dataUrl.slice(0, 24)}-${index}`}>
                  <img src={dataUrl} alt="" />
                  <button
                    className="remove"
                    type="button"
                    onClick={() => setPendingImages((prev) => prev.filter((_, i) => i !== index))}
                  >
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
