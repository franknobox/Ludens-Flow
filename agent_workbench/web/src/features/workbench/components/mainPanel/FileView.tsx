import { useEffect, useState, type ClipboardEvent } from "react";

import { MarkdownRenderer } from "./MarkdownRenderer";
import type { ViewState, WorkspaceFileItem } from "../../types";

interface FileViewProps {
  currentView: ViewState;
  currentProjectId: string;
  fileItems: WorkspaceFileItem[];
  fileCache: Record<string, string>;
  fileEditable: boolean;
  onSaveFile: (fileId: string, content: string) => Promise<void>;
  onUploadFileAsset: (
    fileId: string,
    name: string,
    dataUrl: string,
  ) => Promise<{ markdown: string }>;
}

function fileToDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ""));
    reader.onerror = () => reject(reader.error || new Error("读取图片失败"));
    reader.readAsDataURL(file);
  });
}

export function FileView(props: FileViewProps) {
  const {
    currentView,
    currentProjectId,
    fileItems,
    fileCache,
    fileEditable,
    onSaveFile,
    onUploadFileAsset,
  } = props;

  const [editingFileId, setEditingFileId] = useState<string | null>(null);
  const [fileDraftContent, setFileDraftContent] = useState("");
  const [fileSaveError, setFileSaveError] = useState("");
  const [fileSaveInFlight, setFileSaveInFlight] = useState(false);

  useEffect(() => {
    if (currentView.type !== "file") {
      setEditingFileId(null);
      setFileSaveError("");
      return;
    }
    if (editingFileId && editingFileId !== currentView.id) {
      setEditingFileId(null);
      setFileSaveError("");
    }
  }, [currentView, editingFileId]);

  if (currentView.type !== "file") {
    return null;
  }

  const file = fileItems.find((item) => item.id === currentView.id);
  const content = fileCache[`${currentProjectId}::${currentView.id}`];
  const showContent = typeof content === "string" ? content || "（空）" : "加载中...";
  const canStartEdit = fileEditable && typeof content === "string";
  const isEditing = editingFileId === currentView.id;
  const supportsImagePaste = currentView.id === "notes";

  const startFileEdit = () => {
    if (typeof content !== "string") {
      return;
    }
    setEditingFileId(currentView.id);
    setFileDraftContent(content);
    setFileSaveError("");
  };

  const saveFileEdit = async () => {
    setFileSaveInFlight(true);
    setFileSaveError("");
    try {
      await onSaveFile(currentView.id, fileDraftContent);
      setEditingFileId(null);
    } catch (error) {
      setFileSaveError(error instanceof Error ? error.message : String(error));
    } finally {
      setFileSaveInFlight(false);
    }
  };

  const handleEditorPaste = async (event: ClipboardEvent<HTMLTextAreaElement>) => {
    if (!supportsImagePaste) {
      return;
    }
    const imageFiles = Array.from(event.clipboardData.files || []).filter((item) =>
      item.type.startsWith("image/"),
    );
    if (!imageFiles.length) {
      return;
    }

    event.preventDefault();
    setFileSaveError("");

    const textarea = event.currentTarget;
    const start = textarea.selectionStart ?? fileDraftContent.length;
    const end = textarea.selectionEnd ?? start;

    try {
      const markdownItems: string[] = [];
      for (const image of imageFiles) {
        const dataUrl = await fileToDataUrl(image);
        const uploaded = await onUploadFileAsset(currentView.id, image.name || "pasted-image.png", dataUrl);
        markdownItems.push(uploaded.markdown);
      }

      const insertion = markdownItems.join("\n\n");
      setFileDraftContent((previous) => {
        const next = `${previous.slice(0, start)}${insertion}${previous.slice(end)}`;
        window.requestAnimationFrame(() => {
          const cursor = start + insertion.length;
          textarea.selectionStart = cursor;
          textarea.selectionEnd = cursor;
        });
        return next;
      });
    } catch (error) {
      setFileSaveError(error instanceof Error ? error.message : String(error));
    }
  };

  return (
    <div className="file-panel">
      <div className="file-header">
        <div className="file-title-group">
          <div className="file-title">{file?.name || currentView.id}</div>
          <span className="file-mode-badge">
            {isEditing ? "源码模式" : "渲染预览"}
          </span>
        </div>
        <div className="file-actions">
          {isEditing ? (
            <>
              <button
                type="button"
                className="btn-line btn-file"
                disabled={fileSaveInFlight}
                onClick={() => {
                  setEditingFileId(null);
                  setFileSaveError("");
                }}
              >
                取消
              </button>
              <button
                type="button"
                className="btn btn-file"
                disabled={fileSaveInFlight}
                onClick={() => {
                  void saveFileEdit();
                }}
              >
                {fileSaveInFlight ? "保存中..." : "保存"}
              </button>
            </>
          ) : (
            <button
              type="button"
              className="btn-line btn-file btn-file-icon"
              disabled={!canStartEdit}
              onClick={startFileEdit}
              title={canStartEdit ? "编辑" : "文件加载中，暂不可编辑"}
            >
              {/* pencil icon */}
              <svg viewBox="0 0 16 16" width="13" height="13" fill="currentColor" style={{ marginRight: 4 }}>
                <path d="M11.013 1.427a1.75 1.75 0 0 1 2.474 0l1.086 1.086a1.75 1.75 0 0 1 0 2.474l-8.61 8.61c-.21.21-.47.364-.756.445l-3.251.93a.75.75 0 0 1-.927-.928l.929-3.25c.081-.286.235-.547.445-.758l8.61-8.61Zm.176 4.823L9.75 4.81l-6.286 6.287a.253.253 0 0 0-.064.108l-.558 1.953 1.953-.558a.253.253 0 0 0 .108-.064Zm1.238-3.763a.25.25 0 0 0-.354 0L10.811 3.75l1.439 1.44 1.263-1.263a.25.25 0 0 0 0-.354Z" />
              </svg>
              编辑
            </button>
          )}
        </div>
      </div>

      {isEditing ? (
        <textarea
          className="file-editor"
          value={fileDraftContent}
          disabled={fileSaveInFlight}
          onChange={(event) => setFileDraftContent(event.target.value)}
          onPaste={(event) => {
            void handleEditorPaste(event);
          }}
          placeholder={supportsImagePaste ? "可以直接粘贴图片，图片会保存到 dev_notes/assets/。" : undefined}
        />
      ) : (
        <div className="file-render-view">
          {typeof content === "string" ? (
            content.trim() ? (
              <MarkdownRenderer content={content} className="file-md-body" />
            ) : (
              <div className="file-empty">文件内容为空</div>
            )
          ) : (
            <div className="file-empty">加载中...</div>
          )}
        </div>
      )}

      {fileSaveError ? <div className="file-error">{fileSaveError}</div> : null}
    </div>
  );
}
