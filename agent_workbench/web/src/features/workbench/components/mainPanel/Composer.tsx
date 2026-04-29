import { useRef, useState } from "react";
import type {
  ChangeEvent,
  ClipboardEvent,
  DragEvent,
  KeyboardEvent,
} from "react";

import { agentName } from "../../utils";
import type { AgentKey, ComposerAttachment } from "../../types";

interface ComposerProps {
  agentKey: AgentKey;
  currentAgent: AgentKey;
  projectName: string;
  readOnly: boolean;
  requestInFlight: boolean;
  warningText: string;
  errorText: string;
  onSend: (message: string, attachments: ComposerAttachment[]) => Promise<void>;
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

    return readFileAsDataUrl(blob || file);
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

async function normalizeAttachment(file: File): Promise<ComposerAttachment | null> {
  if (!isSupportedAttachment(file)) {
    return null;
  }

  const kind = file.type.startsWith("image/") ? "image" : "file";
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

async function collectAttachments(files: File[]) {
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

export function Composer(props: ComposerProps) {
  const {
    agentKey,
    currentAgent,
    projectName,
    readOnly,
    requestInFlight,
    warningText,
    errorText,
    onSend,
  } = props;

  const [inputText, setInputText] = useState("");
  const [pendingAttachments, setPendingAttachments] = useState<ComposerAttachment[]>([]);
  const [dragActive, setDragActive] = useState(false);
  const [localWarningText, setLocalWarningText] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);
  const combinedWarningText = [warningText, localWarningText].filter(Boolean).join("\n");

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
      window.alert(`一次最多只能附加 ${MAX_PENDING_ATTACHMENTS} 个项目。`);
    }
    if (!availableSlots) {
      setLocalWarningText(`一次最多只能附加 ${MAX_PENDING_ATTACHMENTS} 个项目。`);
      return;
    }

    const { attachments, warnings } = await collectAttachments(
      files.slice(0, availableSlots),
    );
    setPendingAttachments((prev) =>
      [...prev, ...attachments].slice(0, MAX_PENDING_ATTACHMENTS),
    );
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
              : `在 ${projectName} 中与 ${agentName(agentKey)} 对话...`
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
  );
}
