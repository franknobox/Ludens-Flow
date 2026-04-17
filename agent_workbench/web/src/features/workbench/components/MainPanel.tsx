import { memo, useMemo, useRef, useState } from "react";
import type {
  ChangeEvent,
  ClipboardEvent,
  DragEvent,
  KeyboardEvent,
  RefObject,
} from "react";

import { agentName } from "../utils";
import type {
  AgentKey,
  ComposerAttachment,
  HistoryByAgent,
  RenderMessage,
  TransientChat,
  ViewState,
  WorkflowAction,
  WorkspaceFileItem,
} from "../types";

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
  errorText: string;
  warningText: string;
  contentAreaRef: RefObject<HTMLElement>;
  onSend: (message: string, attachments: ComposerAttachment[]) => Promise<void>;
  onAction: (actionId: string) => void;
}

const MAX_PENDING_ATTACHMENTS = 6;
const MAX_ATTACHMENT_BYTES = 5 * 1024 * 1024;
const IMAGE_MAX_DIMENSION = 1600;
const IMAGE_OUTPUT_QUALITY = 0.82;
const ATTACH_ACCEPT =
  "image/png,image/jpeg,image/webp,image/jpg,.txt,.md,.json,.yaml,.yml,.csv,.cs,.js,.ts,.tsx,.py,.shader,.hlsl,.uxml,.uss,.asmdef,.meta,application/pdf,.pdf";
const ATTACHMENT_EXTENSIONS = new Set([
  ".png",
  ".jpg",
  ".jpeg",
  ".webp",
  ".txt",
  ".md",
  ".json",
  ".yaml",
  ".yml",
  ".csv",
  ".cs",
  ".js",
  ".ts",
  ".tsx",
  ".py",
  ".shader",
  ".hlsl",
  ".uxml",
  ".uss",
  ".asmdef",
  ".meta",
  ".pdf",
]);

function readFileAsDataUrl(file: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ""));
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

function loadImage(sourceUrl: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve(image);
    image.onerror = reject;
    image.src = sourceUrl;
  });
}

async function normalizeImageFile(file: File): Promise<string> {
  const objectUrl = URL.createObjectURL(file);
  try {
    const image = await loadImage(objectUrl);
    const maxDimension = Math.max(image.width, image.height);
    const scale =
      maxDimension > IMAGE_MAX_DIMENSION
        ? IMAGE_MAX_DIMENSION / maxDimension
        : 1;

    const canvas = document.createElement("canvas");
    canvas.width = Math.max(1, Math.round(image.width * scale));
    canvas.height = Math.max(1, Math.round(image.height * scale));

    const context = canvas.getContext("2d");
    if (!context) {
      return readFileAsDataUrl(file);
    }

    context.drawImage(image, 0, 0, canvas.width, canvas.height);
    const blob = await new Promise<Blob | null>((resolve) => {
      canvas.toBlob(resolve, "image/jpeg", IMAGE_OUTPUT_QUALITY);
    });

    if (!blob) {
      return readFileAsDataUrl(file);
    }

    return readFileAsDataUrl(blob);
  } finally {
    URL.revokeObjectURL(objectUrl);
  }
}

function isSupportedAttachment(file: File): boolean {
  const lowerName = file.name.toLowerCase();
  if (file.type.startsWith("image/")) {
    return true;
  }
  return Array.from(ATTACHMENT_EXTENSIONS).some((ext) => lowerName.endsWith(ext));
}

function attachmentKind(file: File): ComposerAttachment["kind"] {
  return file.type.startsWith("image/") ? "image" : "file";
}

async function normalizeAttachment(file: File): Promise<ComposerAttachment | null> {
  if (!isSupportedAttachment(file)) {
    return null;
  }

  const kind = attachmentKind(file);
  const dataUrl =
    kind === "image" ? await normalizeImageFile(file) : await readFileAsDataUrl(file);

  return {
    id: `${file.name}-${file.size}-${file.lastModified}-${Math.random().toString(36).slice(2, 8)}`,
    kind,
    name: file.name,
    mimeType: file.type || "application/octet-stream",
    size: file.size,
    dataUrl,
    previewUrl: kind === "image" ? dataUrl : undefined,
  };
}

interface AttachmentCollectionResult {
  attachments: ComposerAttachment[];
  warnings: string[];
}

async function collectAttachments(files: File[]): Promise<AttachmentCollectionResult> {
  const attachments: ComposerAttachment[] = [];
  const warnings: string[] = [];
  for (const file of files.slice(0, MAX_PENDING_ATTACHMENTS)) {
    if (!isSupportedAttachment(file)) {
      warnings.push(`${file.name}：不支持的文件类型。`);
      continue;
    }
    if (file.size > MAX_ATTACHMENT_BYTES) {
      warnings.push(`${file.name}：文件超过 5 MB。`);
      continue;
    }
    try {
      const attachment = await normalizeAttachment(file);
      if (attachment) {
        attachments.push(attachment);
      } else {
        warnings.push(`${file.name}：不支持的文件类型。`);
      }
    } catch {
      warnings.push(`${file.name}：读取附件失败。`);
    }
  }
  return { attachments, warnings };
}

function attachmentMeta(attachment: ComposerAttachment): string {
  const sizeKb = Math.max(1, Math.round(attachment.size / 1024));
  const kindLabel = attachment.kind === "image" ? "图片" : "文件";
  return `${kindLabel} · ${sizeKb} KB`;
}

function renderMessageRow(agentKey: AgentKey, item: RenderMessage, index: number) {
  const user = item.role === "user";
  const sender = user ? "你" : agentName(agentKey);
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
            <span>思考中</span>
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
  currentProjectId: string,
  fileItems: WorkspaceFileItem[],
  fileCache: Record<string, string>,
) {
  if (currentView.type !== "file") {
    return null;
  }

  const file = fileItems.find((item) => item.id === currentView.id);
  const content = fileCache[`${currentProjectId}::${currentView.id}`];
  const showContent = typeof content === "string" ? content || "（空）" : "加载中...";

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
      if (transientChat.assistantText || transientChat.thinking) {
        rows.push({
          role: "assistant",
          content: transientChat.assistantText || "",
          phase: transientChat.phase,
          thinking: transientChat.thinking && !transientChat.assistantText,
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
              较早的消息已折叠：隐藏 {hiddenCount} 条（当前展示最近 {MAX_RENDER_MESSAGES} 条）。
            </div>
          ) : null}
          {visibleRows.map((item, index) => renderMessageRow(agentKey, item, index))}
        </>
      ) : (
        <div className="empty">
          当前项目里还没有 {agentName(agentKey)} 的对话记录。
        </div>
      )}

      {shouldRenderActions ? (
        <div className="message-actions">
          <p className="title">流程操作</p>
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
    errorText,
    warningText,
    contentAreaRef,
    onSend,
    onAction,
  } = props;

  const [inputText, setInputText] = useState("");
  const [pendingAttachments, setPendingAttachments] = useState<ComposerAttachment[]>([]);
  const [dragActive, setDragActive] = useState(false);
  const [localWarningText, setLocalWarningText] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);
  const combinedWarningText = [warningText, localWarningText].filter(Boolean).join("\n");

  const appendPendingAttachments = (attachments: ComposerAttachment[]) => {
    if (!attachments.length) {
      return;
    }
    setPendingAttachments((prev) =>
      [...prev, ...attachments].slice(0, MAX_PENDING_ATTACHMENTS),
    );
  };

  const processIncomingAttachments = async (
    files: File[],
    options?: { alertOnOverflow?: boolean },
  ) => {
    if (!files.length) {
      return;
    }

    const availableSlots = Math.max(
      0,
      MAX_PENDING_ATTACHMENTS - pendingAttachments.length,
    );
    if (options?.alertOnOverflow && files.length > availableSlots) {
      window.alert(
        `一次最多只能附加 ${MAX_PENDING_ATTACHMENTS} 个项目。`,
      );
    }
    if (!availableSlots) {
      setLocalWarningText(`一次最多只能附加 ${MAX_PENDING_ATTACHMENTS} 个项目。`);
      return;
    }

    const { attachments, warnings } = await collectAttachments(files.slice(0, availableSlots));
    appendPendingAttachments(attachments);
    setLocalWarningText(warnings.join("\n"));
  };

  const handleSend = async () => {
    if (readOnly || requestInFlight) {
      return;
    }

    const text = inputText.trim();
    if (!text && !pendingAttachments.length) {
      return;
    }

    const attachments = pendingAttachments.slice();
    setPendingAttachments([]);
    setInputText("");
    setLocalWarningText("");
    await onSend(text, attachments);
  };

  const handleInputKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void handleSend();
    }
  };

  const handleAttachmentChange = async (event: ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(event.target.files || []);
    event.target.value = "";
    await processIncomingAttachments(files);
  };

  const handleInputPaste = async (event: ClipboardEvent<HTMLTextAreaElement>) => {
    const clipboardItems = Array.from(event.clipboardData?.items || []);
    const imageFiles = clipboardItems
      .filter((item) => item.type.startsWith("image/"))
      .map((item) => item.getAsFile())
      .filter((file): file is File => Boolean(file));

    if (!imageFiles.length) {
      return;
    }

    event.preventDefault();
    await processIncomingAttachments(imageFiles, { alertOnOverflow: true });
  };

  const handleComposerDragOver = (event: DragEvent<HTMLElement>) => {
    const files = Array.from(event.dataTransfer?.files || []);
    if (!files.some((file) => isSupportedAttachment(file))) {
      return;
    }
    event.preventDefault();
    setDragActive(true);
  };

  const handleComposerDragLeave = (event: DragEvent<HTMLElement>) => {
    if (event.currentTarget.contains(event.relatedTarget as Node | null)) {
      return;
    }
    setDragActive(false);
  };

  const handleComposerDrop = async (event: DragEvent<HTMLElement>) => {
    const files = Array.from(event.dataTransfer?.files || []);
    setDragActive(false);
    if (!files.length) {
      return;
    }
    event.preventDefault();
    await processIncomingAttachments(files);
  };

  return (
    <main className="main">
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
          renderFileView(currentView, currentProjectId, fileItems, fileCache)
        )}
      </section>

      {currentView.type === "agent" ? (
        <section
          className={`composer${dragActive ? " drag-active" : ""}`}
          onDragOver={handleComposerDragOver}
          onDragLeave={handleComposerDragLeave}
          onDrop={(event) => {
            void handleComposerDrop(event);
          }}
        >
          <div
            className="attachments"
            style={{ display: pendingAttachments.length ? "flex" : "none" }}
          >
            <div className="attachment-list">
              {pendingAttachments.map((attachment, index) => (
                <div
                  className={`attachment-chip attachment-chip-${attachment.kind}`}
                  key={attachment.id}
                >
                  {attachment.kind === "image" ? (
                    <div className="thumb">
                      <img src={attachment.previewUrl} alt="" />
                    </div>
                  ) : (
                    <div className="attachment-icon">文件</div>
                  )}
                  <div className="attachment-copy">
                    <div className="attachment-name">{attachment.name}</div>
                    <div className="attachment-meta">{attachmentMeta(attachment)}</div>
                  </div>
                  <button
                    className="remove"
                    type="button"
                    onClick={() =>
                      setPendingAttachments((prev) =>
                        prev.filter((_, i) => i !== index),
                      )
                    }
                  >
                    x
                  </button>
                </div>
              ))}
            </div>
          </div>

          <div className="input-row">
            <textarea
              rows={1}
              value={inputText}
              disabled={readOnly || requestInFlight}
              onChange={(event) => setInputText(event.target.value)}
              onKeyDown={handleInputKeyDown}
              onPaste={(event) => {
                void handleInputPaste(event);
              }}
              placeholder={
                readOnly
                  ? `当前是只读历史记录。当前活跃 Agent 为 ${agentName(currentAgent)}。`
                  : `在 ${projectName} 中与 ${agentName(currentView.id)} 对话...`
              }
            />
            <input
              ref={fileInputRef}
              type="file"
              accept={ATTACH_ACCEPT}
              multiple
              style={{ display: "none" }}
              onChange={(event) => {
                void handleAttachmentChange(event);
              }}
            />
            <button
              className="btn-line"
              type="button"
              disabled={readOnly || requestInFlight}
              onClick={() => fileInputRef.current?.click()}
            >
              附件
            </button>
            <button
              className="btn"
              type="button"
              disabled={readOnly || requestInFlight}
              onClick={() => {
                void handleSend();
              }}
            >
              发送
            </button>
          </div>

          <div className="warning">{combinedWarningText || ""}</div>
          <div className="error">{errorText || ""}</div>
        </section>
      ) : null}
    </main>
  );
}



