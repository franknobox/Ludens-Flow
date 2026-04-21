import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";

import { workbenchApi } from "./api";
import { PHASE_LABEL } from "./constants";
import { useProjectRuntime } from "./state/ProjectRuntimeContext";
import { LeftSidebar } from "./components/LeftSidebar";
import { MainPanel } from "./components/MainPanel";
import { RightSidebar } from "./components/RightSidebar";
import {
  agentName,
  buildHistoryByAgent,
  phaseToAgent,
  projectUpdated,
  toErrorMessage,
  transientMessageText,
} from "./utils";
import type {
  ChatResponse,
  ComposerAttachment,
  StateResponse,
  TransientChat,
  ToolProgressEvent,
  ViewState,
  WorkbenchEvent,
  WorkbenchStateModel,
} from "./types";

const INITIAL_MODEL: WorkbenchStateModel = {
  project_id: "",
  phase: "",
  current_agent: "design",
  iteration_count: 0,
  artifact_frozen: false,
  review_gate: null,
  transcript_history: [],
  chat_history: [],
  files: [],
  projects: [],
  active_projects: [],
  archived_projects: [],
  actions: [],
};

const TRANSIENT_CHAT_STORAGE_KEY = "ludensflow.workbench.transientChat";

function toModelState(state: StateResponse): WorkbenchStateModel {
  return {
    project_id: state.project_id || "",
    phase: state.phase || "",
    current_agent: state.current_agent || phaseToAgent(state.phase),
    iteration_count: state.iteration_count || 0,
    artifact_frozen: !!state.artifact_frozen,
    review_gate: state.review_gate || null,
    transcript_history: state.transcript_history || [],
    chat_history: state.chat_history || [],
    files: [],
    projects: [],
    active_projects: [],
    archived_projects: [],
    actions: state.actions || [],
  };
}

function mergeChatResponse(
  prev: WorkbenchStateModel,
  response: ChatResponse,
): WorkbenchStateModel {
  return {
    ...prev,
    phase: response.phase || prev.phase,
    current_agent: phaseToAgent(response.phase || prev.phase),
    review_gate: response.review_gate || prev.review_gate,
    actions: response.actions || [],
  };
}

function fileCacheKey(projectId: string, fileId: string): string {
  return `${projectId}::${fileId}`;
}

function loadStoredTransientChat(): {
  projectId: string;
  transientChat: TransientChat;
  requestInFlight: boolean;
} | null {
  try {
    const raw = window.sessionStorage.getItem(TRANSIENT_CHAT_STORAGE_KEY);
    if (!raw) {
      return null;
    }
    return JSON.parse(raw) as {
      projectId: string;
      transientChat: TransientChat;
      requestInFlight: boolean;
    };
  } catch {
    return null;
  }
}

type WorkbenchPageProps = {
  isActive?: boolean;
};

export function WorkbenchPage({ isActive = false }: WorkbenchPageProps) {
  const {
    runtimeState,
    projects,
    activeProjects: runtimeActiveProjects,
    archivedProjects: runtimeArchivedProjects,
    refreshRuntime,
    selectProject,
    createProject: createRuntimeProject,
    subscribeEvents,
  } = useProjectRuntime();

  const [model, setModel] = useState<WorkbenchStateModel>(INITIAL_MODEL);
  const [currentView, setCurrentView] = useState<ViewState>({
    type: "agent",
    id: "design",
  });
  const [fileCache, setFileCache] = useState<Record<string, string>>({});
  const [requestInFlight, setRequestInFlight] = useState(false);
  const [transientChat, setTransientChat] = useState<TransientChat | null>(null);
  const [errorText, setErrorText] = useState("");
  const [warningText, setWarningText] = useState("");
  const [projectPanelOpen, setProjectPanelOpen] = useState(false);
  const [projectCreateMode, setProjectCreateMode] = useState(false);
  const [projectTitleDraft, setProjectTitleDraft] = useState("");
  const [projectSettingsOpen, setProjectSettingsOpen] = useState(false);
  const [renameDraft, setRenameDraft] = useState("");
  const [archiveSubmitting, setArchiveSubmitting] = useState(false);

  const contentAreaRef = useRef<HTMLElement>(null);
  const lastEventAtRef = useRef(0);
  const lastSyncedProjectIdRef = useRef("");
  const projectPanelRef = useRef<HTMLDivElement>(null);
  const projectPanelButtonRef = useRef<HTMLButtonElement>(null);
  const projectSettingsPanelRef = useRef<HTMLDivElement>(null);
  const projectSettingsButtonRef = useRef<HTMLButtonElement>(null);
  const [topbarSlot, setTopbarSlot] = useState<HTMLElement | null>(null);

  const historyByAgent = useMemo(() => buildHistoryByAgent(model), [model]);
  const activeProject = useMemo(
    () => runtimeActiveProjects.find((p) => p.id === runtimeState?.project_id),
    [runtimeActiveProjects, runtimeState?.project_id],
  );
  const activeProjects = runtimeActiveProjects.length ? runtimeActiveProjects : projects;
  const projectName = activeProject?.display_name || model.project_id || "未选择项目";
  const readOnly = currentView.type !== "agent" || currentView.id !== model.current_agent;

  const statusNote = useMemo(() => {
    if (activeProject?.archived) {
      return "当前项目已经归档，你仍然可以查看它的状态与工件。";
    }
    if (model.artifact_frozen) {
      return "当前项目处于持续开发辅导阶段，主工件已经冻结。";
    }
    if (activeProject?.last_message_preview) {
      return activeProject.last_message_preview;
    }
    return "当前项目的状态、工件、图片和日志都会保留在这个项目里。";
  }, [activeProject, model.artifact_frozen]);

  const clearTransientChat = () => {
    setTransientChat(null);
    window.sessionStorage.removeItem(TRANSIENT_CHAT_STORAGE_KEY);
  };

  const closeProjectPanel = () => {
    setProjectPanelOpen(false);
    setProjectCreateMode(false);
    setProjectTitleDraft("");
  };

  const closeProjectSettings = () => {
    setProjectSettingsOpen(false);
    setRenameDraft("");
  };

  const handleRenameProject = async () => {
    const trimmed = renameDraft.trim();
    if (!trimmed || !activeProject) return;
    try {
      await workbenchApi.renameProject(activeProject.id, trimmed);
      await refreshRuntime();
      setRenameDraft("");
      setProjectSettingsOpen(false);
    } catch (error) {
      setErrorText("重命名失败：" + toErrorMessage(error));
    }
  };

  const handleArchiveProject = async () => {
    if (!activeProject || activeProject.archived) return;
    const confirmed = window.confirm(
      `要将“${activeProject.display_name || activeProject.id}”归档吗？\n\n归档后它会从当前项目列表中移除，可以从设置页历史项目中恢复。`,
    );
    if (!confirmed) return;
    setArchiveSubmitting(true);
    try {
      await workbenchApi.archiveProject(activeProject.id);
      await refreshRuntime();
      setProjectSettingsOpen(false);
    } catch (error) {
      setErrorText("归档失败：" + toErrorMessage(error));
    } finally {
      setArchiveSubmitting(false);
    }
  };

  const syncFilesOnly = async () => {
    const files = await workbenchApi.getWorkspaceFiles();
    setModel((prev) => ({
      ...prev,
      files: files.files || [],
    }));
  };

  const hardRefresh = async () => {
    await Promise.all([refreshRuntime(), syncFilesOnly()]);
  };

  const handleWorkbenchEvent = (event: WorkbenchEvent) => {
    lastEventAtRef.current = Date.now();

    if (event.type === "run_started") {
      setRequestInFlight(true);
      setTransientChat((prev) =>
        prev
          ? prev
          : {
              agentKey: event.current_agent || phaseToAgent(event.phase || ""),
              phase: event.phase || "",
              userText: event.message || "[处理中]",
              thinking: true,
              assistantText: "",
              toolEvents: [],
            },
      );
      return;
    }

    if (
      event.type === "tool_started" ||
      event.type === "tool_completed" ||
      event.type === "tool_failed"
    ) {
      setTransientChat((prev) => {
        const toolEventType = event.type as ToolProgressEvent["type"];
        const nextEvent: ToolProgressEvent = {
          id: `${Date.now()}-${event.type}-${event.tool_name || "tool"}`,
          type: toolEventType,
          tool_name: event.tool_name || "tool",
          tool_summary: event.tool_summary || (event.tool_name || "工具调用"),
          tool_result_summary: event.tool_result_summary,
          error: event.error,
        };

        if (prev) {
          return {
            ...prev,
            toolEvents: [...(prev.toolEvents || []), nextEvent],
          };
        }

        return {
          agentKey: event.current_agent || phaseToAgent(event.phase || ""),
          phase: event.phase || "",
          userText: "[处理中]",
          thinking: true,
          assistantText: "",
          toolEvents: [nextEvent],
        };
      });
      return;
    }

    if (event.type === "assistant_stream_started") {
      setTransientChat((prev) =>
        prev
          ? {
              ...prev,
              thinking: true,
              assistantText: prev.assistantText || "",
            }
          : {
              agentKey: event.current_agent || phaseToAgent(event.phase || ""),
              phase: event.phase || "",
              userText: "[处理中]",
              thinking: true,
              assistantText: "",
              toolEvents: [],
            },
      );
      return;
    }

    if (event.type === "assistant_delta") {
      setTransientChat((prev) =>
        prev
          ? {
              ...prev,
              thinking: false,
              assistantText: `${prev.assistantText || ""}${event.delta || ""}`,
            }
          : {
              agentKey: event.current_agent || phaseToAgent(event.phase || ""),
              phase: event.phase || "",
              userText: "[处理中]",
              thinking: false,
              assistantText: event.delta || "",
              toolEvents: [],
            },
      );
      return;
    }

    if (event.type === "assistant_stream_completed") {
      setTransientChat((prev) => (prev ? { ...prev, thinking: false } : prev));
      return;
    }

    if (event.type === "state_updated" || event.type === "connected") {
      setCurrentView((prev) =>
        prev.type === "agent"
          ? {
              type: "agent",
              id: event.state?.current_agent || phaseToAgent(event.state?.phase || ""),
            }
          : prev,
      );
      clearTransientChat();
      setRequestInFlight(false);
      return;
    }

    if (event.type === "run_failed") {
      clearTransientChat();
      setRequestInFlight(false);
      setErrorText(event.error || "请求失败。");
      setWarningText("");
    }
  };

  const openProject = async (projectId: string) => {
    if (!projectId) return;
    if (projectId === model.project_id) {
      closeProjectPanel();
      return;
    }

    setErrorText("");
    setWarningText("");
    try {
      await selectProject(projectId);
      clearTransientChat();
      setFileCache({});
      closeProjectPanel();
      void syncFilesOnly().catch(() => {
        // workspace files can refresh lazily
      });
    } catch (error) {
      setErrorText("切换项目失败：" + toErrorMessage(error));
    }
  };

  const openFile = async (fileId: string) => {
    setCurrentView({ type: "file", id: fileId });
    const cacheKey = fileCacheKey(model.project_id, fileId);
    if (Object.prototype.hasOwnProperty.call(fileCache, cacheKey)) {
      return;
    }

    try {
      const data = await workbenchApi.getWorkspaceFileContent(fileId);
      setFileCache((prev) => ({ ...prev, [cacheKey]: data.content || "" }));
    } catch (error) {
      setFileCache((prev) => ({
        ...prev,
        [cacheKey]: `加载失败：${toErrorMessage(error)}`,
      }));
    }
  };

  const saveWorkspaceFile = async (fileId: string, content: string) => {
    try {
      const data = await workbenchApi.updateWorkspaceFileContent(fileId, content);
      const cacheKey = fileCacheKey(model.project_id, fileId);
      setFileCache((prev) => ({ ...prev, [cacheKey]: data.content || "" }));

      const updatedState = data.state;
      if (updatedState) {
        setModel((prev) => ({
          ...prev,
          ...toModelState(updatedState),
          files: prev.files,
        }));
      }
      void refreshRuntime().catch(() => {
        // do not block save completion on runtime metadata refresh
      });
    } catch (error) {
      throw new Error(`保存失败：${toErrorMessage(error)}`);
    }
  };

  const createProject = async (title: string): Promise<boolean> => {
    const displayName = title.trim();
    if (!displayName) {
      setErrorText("请输入项目名称。");
      return false;
    }

    setErrorText("");
    try {
      await createRuntimeProject(displayName);
      clearTransientChat();
      setFileCache({});
      closeProjectPanel();
      void syncFilesOnly().catch(() => {
        // workspace files can refresh lazily
      });
      return true;
    } catch (error) {
      setErrorText("创建项目失败：" + toErrorMessage(error));
      return false;
    }
  };

  const sendMessage = async (text: string, attachments: ComposerAttachment[]) => {
    if (!text && !attachments.length) {
      return;
    }

    setErrorText("");
    setWarningText("");
    setRequestInFlight(true);
    setTransientChat({
      agentKey: model.current_agent,
      phase: model.phase,
      userText: transientMessageText(text, attachments),
      thinking: true,
      toolEvents: [],
    });

    try {
      const response = await workbenchApi.postChat({
        message: text,
        attachments: attachments.map((item) => ({
          kind: item.kind,
          name: item.name,
          mime_type: item.mimeType,
          data_url: item.dataUrl,
          size: item.size,
        })),
      });
      if (response.error) {
        setErrorText(response.error);
      }
      setWarningText((response.attachment_warnings || []).join("\n"));
      setModel((prev) => mergeChatResponse(prev, response));
      setFileCache({});
      window.setTimeout(() => {
        if (Date.now() - lastEventAtRef.current > 800) {
          void refreshRuntime();
          clearTransientChat();
        }
      }, 600);
    } catch (error) {
      setTransientChat((prev) => (prev ? { ...prev, thinking: false } : prev));
      setErrorText("请求失败：" + toErrorMessage(error));
      setWarningText("");
    } finally {
      setRequestInFlight(false);
    }
  };

  const sendAction = async (actionId: string) => {
    if (!actionId || requestInFlight || readOnly || currentView.type !== "agent") {
      return;
    }

    setErrorText("");
    setWarningText("");
    setRequestInFlight(true);
    setTransientChat({
      agentKey: currentView.id,
      phase: model.phase,
      userText: `[操作] ${actionId}`,
      thinking: true,
      toolEvents: [],
    });

    try {
      const response = await workbenchApi.postAction(actionId);
      if (response.error) {
        setErrorText(response.error);
      }
      setWarningText("");
      setModel((prev) => mergeChatResponse(prev, response));
      setFileCache({});
      window.setTimeout(() => {
        if (Date.now() - lastEventAtRef.current > 800) {
          void refreshRuntime();
          clearTransientChat();
        }
      }, 600);
    } catch (error) {
      setTransientChat((prev) => (prev ? { ...prev, thinking: false } : prev));
      setErrorText("执行操作失败：" + toErrorMessage(error));
      setWarningText("");
    } finally {
      setRequestInFlight(false);
    }
  };

  useEffect(() => {
    if (!runtimeState) {
      return;
    }

    setModel((prev) => ({
      ...prev,
      ...toModelState(runtimeState),
      projects,
      active_projects: runtimeActiveProjects,
      archived_projects: runtimeArchivedProjects,
      files: prev.files,
    }));
    setCurrentView((prev) =>
      prev.type === "agent"
        ? {
            type: "agent",
            id: runtimeState.current_agent || phaseToAgent(runtimeState.phase),
          }
        : prev,
    );
  }, [runtimeState, projects, runtimeActiveProjects, runtimeArchivedProjects]);

  useEffect(() => {
    if (!model.project_id || lastSyncedProjectIdRef.current === model.project_id) {
      return;
    }
    lastSyncedProjectIdRef.current = model.project_id;
    setFileCache({});
    void syncFilesOnly().catch(() => {
      // keep UI responsive even if artifact list refresh is delayed
    });
  }, [model.project_id]);

  useEffect(() => {
    void hardRefresh().catch((error) => {
      setErrorText("加载失败：" + toErrorMessage(error));
    });
  }, []);

  useEffect(() => {
    if (!model.project_id) {
      return;
    }

    const stored = loadStoredTransientChat();
    if (!stored || stored.projectId !== model.project_id || transientChat) {
      return;
    }
    setTransientChat(stored.transientChat);
    setRequestInFlight(Boolean(stored.requestInFlight));
  }, [model.project_id, transientChat]);

  useEffect(() => {
    if (!model.project_id || !transientChat) {
      window.sessionStorage.removeItem(TRANSIENT_CHAT_STORAGE_KEY);
      return;
    }
    try {
      window.sessionStorage.setItem(
        TRANSIENT_CHAT_STORAGE_KEY,
        JSON.stringify({
          projectId: model.project_id,
          transientChat,
          requestInFlight,
        }),
      );
    } catch {
      // ignore storage failures
    }
  }, [model.project_id, transientChat, requestInFlight]);

  useEffect(() => {
    return subscribeEvents(handleWorkbenchEvent);
  }, [subscribeEvents]);

  useEffect(() => {
    setTopbarSlot(document.getElementById("topbar-center-slot"));
  }, []);

  useEffect(() => {
    if (!projectPanelOpen) {
      return;
    }

    const handlePointerDown = (event: MouseEvent) => {
      const target = event.target as Node | null;
      if (
        projectPanelRef.current?.contains(target) ||
        projectPanelButtonRef.current?.contains(target)
      ) {
        return;
      }
      closeProjectPanel();
    };

    document.addEventListener("mousedown", handlePointerDown);
    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
    };
  }, [projectPanelOpen]);

  useEffect(() => {
    if (!projectSettingsOpen) {
      return;
    }

    const handlePointerDown = (event: MouseEvent) => {
      const target = event.target as Node | null;
      if (
        projectSettingsPanelRef.current?.contains(target) ||
        projectSettingsButtonRef.current?.contains(target)
      ) {
        return;
      }
      closeProjectSettings();
    };

    document.addEventListener("mousedown", handlePointerDown);
    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
    };
  }, [projectSettingsOpen]);

  useEffect(() => {
    if (currentView.type !== "agent") {
      return;
    }

    const area = contentAreaRef.current;
    if (!area) {
      return;
    }

    const distanceToBottom = area.scrollHeight - area.scrollTop - area.clientHeight;
    const shouldStickToBottom = distanceToBottom < 120 || Boolean(transientChat?.thinking);
    if (!shouldStickToBottom) {
      return;
    }

    const id = window.requestAnimationFrame(() => {
      area.scrollTop = area.scrollHeight;
    });
    return () => window.cancelAnimationFrame(id);
  }, [currentView, historyByAgent, transientChat, model.actions]);

  const title =
    currentView.type === "agent"
      ? agentName(currentView.id)
      : model.files.find((item) => item.id === currentView.id)?.name || currentView.id;

  const subtitle =
    currentView.type === "agent"
      ? `当前项目：${projectName} · 当前 Agent：${agentName(model.current_agent)}`
      : `正在查看 ${projectName} 内的工件`;

  const projectToolbar = (
    <div className="project-toolbar">
      <div className="project-toolbar-info">
        <div className="project-toolbar-meta">
          <span className="project-toolbar-label">项目名</span>
          <strong>{projectName}</strong>
        </div>
        <div className="project-toolbar-meta">
          <span className="project-toolbar-label">项目阶段</span>
          <strong>{PHASE_LABEL[model.phase] || model.phase || "-"}</strong>
        </div>
        <div className="project-toolbar-meta">
          <span className="project-toolbar-label">更新时间</span>
          <strong>{projectUpdated(activeProject)}</strong>
        </div>
      </div>

      <div className="project-toolbar-menu">
        <button
          ref={projectPanelButtonRef}
          type="button"
          className={`project-toolbar-toggle${projectPanelOpen ? " is-active" : ""}`}
          onClick={() => {
            if (projectPanelOpen) {
              closeProjectPanel();
              return;
            }
            setProjectSettingsOpen(false);
            setProjectPanelOpen(true);
          }}
        >
          项目选单
        </button>

        <button
          ref={projectSettingsButtonRef}
          type="button"
          className={`project-toolbar-settings${projectSettingsOpen ? " is-active" : ""}`}
          onClick={() => {
            if (projectSettingsOpen) {
              closeProjectSettings();
              return;
            }
            setProjectPanelOpen(false);
            setRenameDraft(activeProject?.display_name || activeProject?.title || "");
            setProjectSettingsOpen(true);
          }}
          title="项目设置"
        >
          ⚙
        </button>

        {projectSettingsOpen ? (
          <div ref={projectSettingsPanelRef} className="project-toolbar-panel project-toolbar-settings-panel">
            <div className="project-toolbar-panel-title">项目设置</div>

            <div className="project-toolbar-settings-section">
              <div className="project-toolbar-settings-label">重命名项目</div>
              <div className="project-toolbar-settings-row">
                <input
                  className="project-toolbar-settings-input"
                  type="text"
                  value={renameDraft}
                  onChange={(event) => setRenameDraft(event.target.value)}
                  placeholder="输入新名称"
                  onKeyDown={(event) => {
                    if (event.key === "Enter" && renameDraft.trim()) {
                      void handleRenameProject();
                    }
                  }}
                />
                <button
                  type="button"
                  className="shell-btn primary compact"
                  disabled={!renameDraft.trim() || renameDraft === (activeProject?.display_name || activeProject?.title)}
                  onClick={() => {
                    void handleRenameProject();
                  }}
                >
                  确认
                </button>
              </div>
            </div>

            {!activeProject?.archived ? (
              <div className="project-toolbar-settings-section">
                <div className="project-toolbar-settings-label">归档项目</div>
                <button
                  type="button"
                  className="shell-btn danger compact"
                  disabled={archiveSubmitting}
                  onClick={() => {
                    void handleArchiveProject();
                  }}
                >
                  {archiveSubmitting ? "归档中…" : "归档当前项目"}
                </button>
              </div>
            ) : null}
          </div>
        ) : null}

        {projectPanelOpen ? (
          <div ref={projectPanelRef} className="project-toolbar-panel">
            {!projectCreateMode ? (
              <>
                <div className="project-toolbar-panel-title">切换项目</div>
                <div className="project-toolbar-list">
                  {activeProjects.map((project) => (
                    <button
                      key={project.id}
                      type="button"
                      className={`project-toolbar-item${
                        project.id === model.project_id ? " is-active" : ""
                      }`}
                      onClick={() => {
                        void openProject(project.id);
                      }}
                    >
                      <div className="project-toolbar-item-head">
                        <strong className="project-toolbar-item-name">
                          {project.display_name || project.id}
                        </strong>
                        <div className="project-toolbar-item-meta-row">
                          <span className="project-toolbar-item-sub">
                            {PHASE_LABEL[
                              project.id === model.project_id
                                ? model.phase || project.last_phase || ""
                                : project.last_phase || ""
                            ] ||
                              (project.id === model.project_id
                                ? model.phase || project.last_phase || "暂无阶段"
                                : project.last_phase || "暂无阶段")}
                          </span>
                          <span className="project-toolbar-item-sub">
                            {projectUpdated(project)}
                          </span>
                        </div>
                        {project.id === model.project_id ? (
                          <span className="tag active">当前</span>
                        ) : null}
                      </div>
                    </button>
                  ))}
                </div>
                <button
                  type="button"
                  className="project-toolbar-create-entry"
                  onClick={() => {
                    setProjectCreateMode(true);
                    setProjectTitleDraft("");
                  }}
                >
                  <span>新建项目</span>
                  <span className="project-toolbar-create-plus">+</span>
                </button>
              </>
            ) : (
              <div className="project-toolbar-create">
                <div className="project-toolbar-panel-title">新建项目</div>
                <input
                  value={projectTitleDraft}
                  onChange={(event) => setProjectTitleDraft(event.target.value)}
                  type="text"
                  placeholder="输入项目名称"
                  autoFocus
                />
                <div className="project-toolbar-create-actions">
                  <button
                    type="button"
                    className="shell-btn primary"
                    onClick={() => {
                      void createProject(projectTitleDraft);
                    }}
                  >
                    确认新建
                  </button>
                  <button
                    type="button"
                    className="shell-btn"
                    onClick={() => {
                      setProjectCreateMode(false);
                      setProjectTitleDraft("");
                    }}
                  >
                    取消
                  </button>
                </div>
              </div>
            )}
          </div>
        ) : null}
      </div>
    </div>
  );

  return (
    <div className="app">
      <LeftSidebar
        files={model.files}
        currentView={currentView}
        onOpenFile={(fileId) => {
          void openFile(fileId);
        }}
      />

      <div className="workspace-column">
        {isActive && topbarSlot ? createPortal(projectToolbar, topbarSlot) : null}

        <MainPanel
          currentView={currentView}
          currentProjectId={model.project_id}
          currentAgent={model.current_agent}
          projectName={projectName}
          phaseLabel={PHASE_LABEL[model.phase] || model.phase || "-"}
          modeBadge={currentView.type === "agent" ? "Agent 对话" : "文件查看"}
          readOnly={readOnly}
          subtitle={subtitle}
          title={title}
          historyByAgent={historyByAgent}
          transientChat={transientChat}
          actions={model.actions}
          requestInFlight={requestInFlight}
          fileItems={model.files}
          fileCache={fileCache}
          fileEditable={!activeProject?.archived}
          errorText={errorText}
          warningText={warningText}
          contentAreaRef={contentAreaRef}
          onSend={async (message, attachments) => {
            if (currentView.type !== "agent" || readOnly || requestInFlight) {
              return;
            }
            await sendMessage(message, attachments);
          }}
          onAction={(actionId) => {
            void sendAction(actionId);
          }}
          onSaveFile={async (fileId, content) => {
            await saveWorkspaceFile(fileId, content);
          }}
        />
      </div>

      <RightSidebar
        currentView={currentView}
        currentAgent={model.current_agent}
        projectName={projectName}
        phaseLabel={PHASE_LABEL[model.phase] || model.phase || "-"}
        iterationCount={model.iteration_count || 0}
        filesCount={model.files.length}
        modeLabel={readOnly ? "只读" : "可写"}
        statusUpdated={projectUpdated(activeProject)}
        statusLastPhase={activeProject?.last_phase || "-"}
        statusNote={statusNote}
        activeProject={activeProject}
        onSelectAgent={(agent) => {
          setCurrentView({ type: "agent", id: agent });
        }}
      />
    </div>
  );
}
