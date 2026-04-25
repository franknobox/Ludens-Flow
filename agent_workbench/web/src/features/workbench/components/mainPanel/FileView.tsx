import { useEffect, useState } from "react";

import type { ViewState, WorkspaceFileItem } from "../../types";

interface FileViewProps {
  currentView: ViewState;
  currentProjectId: string;
  fileItems: WorkspaceFileItem[];
  fileCache: Record<string, string>;
  fileEditable: boolean;
  onSaveFile: (fileId: string, content: string) => Promise<void>;
}

export function FileView(props: FileViewProps) {
  const {
    currentView,
    currentProjectId,
    fileItems,
    fileCache,
    fileEditable,
    onSaveFile,
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

  return (
    <div className="file-panel">
      <div className="file-header">
        <div className="file-title">{file?.name || currentView.id}</div>
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
              title={canStartEdit ? "编辑工件" : "文件加载中，暂不可编辑"}
            >
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
        />
      ) : (
        <pre className="file-content">{showContent}</pre>
      )}

      {fileSaveError ? <div className="file-error">{fileSaveError}</div> : null}
    </div>
  );
}
