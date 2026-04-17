import { useEffect, useMemo, useRef, useState } from "react";

import { PHASE_LABEL } from "./constants";
import { workbenchApi } from "./api";
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

function mergeChatResponse(prev: WorkbenchStateModel, response: ChatResponse): WorkbenchStateModel {
  return {
    ...prev,
    phase: response.phase || prev.phase,
    current_agent: phaseToAgent(response.phase || prev.phase),
    review_gate: response.review_gate || prev.review_gate,
    actions: response.actions || [],
  };
}

function applyStateSnapshot(
  prev: WorkbenchStateModel,
  state: StateResponse,
  projects?: WorkbenchStateModel["projects"],
  activeProjects?: WorkbenchStateModel["active_projects"],
  archivedProjects?: WorkbenchStateModel["archived_projects"],
): WorkbenchStateModel {
  return {
    ...toModelState(state),
    projects: projects || prev.projects,
    active_projects: activeProjects || prev.active_projects,
    archived_projects: archivedProjects || prev.archived_projects,
    files: prev.files,
  };
}

function fileCacheKey(projectId: string, fileId: string): string {
  return `${projectId}::${fileId}`;
}

export function WorkbenchPage() {
  const [model, setModel] = useState<WorkbenchStateModel>(INITIAL_MODEL);
  const [currentView, setCurrentView] = useState<ViewState>({ type: "agent", id: "design" });
  const [sidebarMode, setSidebarMode] = useState<"projects" | "project" | "history">("projects");
  const [fileCache, setFileCache] = useState<Record<string, string>>({});
  const [requestInFlight, setRequestInFlight] = useState(false);
  const [transientChat, setTransientChat] = useState<TransientChat | null>(null);
  const [errorText, setErrorText] = useState("");
  const [warningText, setWarningText] = useState("");

  const contentAreaRef = useRef<HTMLElement>(null);
  const lastEventAtRef = useRef(0);

  const historyByAgent = useMemo(() => buildHistoryByAgent(model), [model]);
  const activeProject = useMemo(
    () => model.projects.find((project) => project.id === model.project_id),
    [model.project_id, model.projects],
  );
  const projectName = activeProject?.display_name || model.project_id || "项目";

  const readOnly = currentView.type !== "agent" || currentView.id !== model.current_agent;

  const statusNote = useMemo(() => {
    if (activeProject?.archived) {
      return "当前项目已归档，你仍然可以查看它的本地状态和工件。";
    }
    if (model.artifact_frozen) {
      return "当前项目处于持续开发辅导阶段，主工件已冻结。";
    }
    if (activeProject?.last_message_preview) {
      return activeProject.last_message_preview;
    }
    return "当前项目可写，状态、工件、画像和日志都会保留在这个项目内。";
  }, [activeProject, model.artifact_frozen]);

  const syncStateOnly = async (): Promise<StateResponse> => {
    const state = await workbenchApi.getState();
    setModel((prev) => ({
      ...toModelState(state),
      projects: prev.projects,
      active_projects: prev.active_projects,
      archived_projects: prev.archived_projects,
      files: prev.files,
    }));
    return state;
  };

  const syncProjectsOnly = async () => {
    const data = await workbenchApi.getProjects();
    setModel((prev) => ({
      ...prev,
      projects: data.projects || [],
      active_projects: data.active_projects || data.projects || [],
      archived_projects: data.archived_projects || [],
    }));
  };

  const hardRefresh = async () => {
    const [state, projects, files] = await Promise.all([
      workbenchApi.getState(),
      workbenchApi.getProjects(),
      workbenchApi.getWorkspaceFiles(),
    ]);

    setModel((prev) => ({
      ...toModelState(state),
      projects: projects.projects || [],
      active_projects: projects.active_projects || projects.projects || [],
      archived_projects: projects.archived_projects || [],
      files: files.files || [],
    }));
    setCurrentView({
      type: "agent",
      id: state.current_agent || phaseToAgent(state.phase),
    });
  };

  const handleWorkbenchEvent = (event: WorkbenchEvent) => {
    lastEventAtRef.current = Date.now();

    if (event.type === "projects_updated") {
      setModel((prev) => ({
        ...prev,
        projects: event.projects || prev.projects,
        active_projects: event.active_projects || event.projects || prev.active_projects,
        archived_projects: event.archived_projects || prev.archived_projects,
      }));
      return;
    }

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
            },
      );
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
            },
      );
      return;
    }

    if (event.type === "assistant_stream_completed") {
      setTransientChat((prev) => (prev ? { ...prev, thinking: false } : prev));
      return;
    }

    if (event.type === "state_updated" || event.type === "connected") {
      if (event.state) {
        setModel((prev) =>
          applyStateSnapshot(
            prev,
            event.state as StateResponse,
            event.projects,
            event.active_projects || event.projects,
            event.archived_projects,
          ),
        );
        setCurrentView((prev) =>
          prev.type === "agent"
            ? {
                type: "agent",
                id: event.state?.current_agent || phaseToAgent(event.state?.phase || ""),
              }
            : prev,
        );
      }
      setTransientChat(null);
      setRequestInFlight(false);
      return;
    }

    if (event.type === "run_failed") {
      if (event.state) {
        setModel((prev) =>
          applyStateSnapshot(
            prev,
            event.state as StateResponse,
            event.projects,
            event.active_projects || event.projects,
            event.archived_projects,
          ),
        );
      }
      setTransientChat(null);
      setRequestInFlight(false);
      setErrorText(event.error || "请求失败。");
      setWarningText("");
    }
  };

  const openProject = async (projectId: string) => {
    if (!projectId) return;
    setSidebarMode("project");
    if (projectId === model.project_id) {
      return;
    }

    setErrorText("");
    setWarningText("");
    try {
      await workbenchApi.selectProject(projectId);
      await hardRefresh();
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

  const createProject = async (projectId: string, title: string): Promise<boolean> => {
    if (!projectId) {
      setErrorText("项目 ID 不能为空。");
      return false;
    }

    setErrorText("");
    try {
      await workbenchApi.createProject({
        project_id: projectId,
        display_name: title || null,
      });
      setSidebarMode("project");
      await hardRefresh();
      return true;
    } catch (error) {
      setErrorText("创建项目失败：" + toErrorMessage(error));
      return false;
    }
  };

  const renameProject = async (projectId: string, displayName: string): Promise<boolean> => {
    setErrorText("");
    try {
      await workbenchApi.renameProject(projectId, displayName);
      await hardRefresh();
      return true;
    } catch (error) {
      setErrorText("重命名项目失败：" + toErrorMessage(error));
      return false;
    }
  };

  const archiveProject = async (projectId: string) => {
    const target = model.projects.find((project) => project.id === projectId);
    const yes = window.confirm(
      `要归档 ${target?.display_name || projectId} 吗？\n\n项目会移动到“历史项目”，之后仍可恢复。`,
    );
    if (!yes) {
      return;
    }

    setErrorText("");
    try {
      await workbenchApi.archiveProject(projectId);
      setTransientChat(null);
      setFileCache({});
      if (projectId === model.project_id) {
        setSidebarMode("projects");
      }
      await hardRefresh();
    } catch (error) {
      setErrorText("归档项目失败：" + toErrorMessage(error));
    }
  };

  const restoreProject = async (projectId: string) => {
    const target = model.archived_projects.find((project) => project.id === projectId);
    const yes = window.confirm(
      `要恢复 ${target?.display_name || projectId} 吗？\n\n项目会重新回到当前项目列表。`,
    );
    if (!yes) {
      return;
    }

    setErrorText("");
    try {
      await workbenchApi.restoreProject(projectId, false);
      await hardRefresh();
    } catch (error) {
      setErrorText("恢复项目失败：" + toErrorMessage(error));
    }
  };

  const deleteProject = async (projectId: string) => {
    const target = model.archived_projects.find((project) => project.id === projectId);
    const yes = window.confirm(
      `要永久删除 ${target?.display_name || projectId} 吗？\n\n这会删除已归档项目目录，而且无法撤销。`,
    );
    if (!yes) {
      return;
    }

    setErrorText("");
    try {
      await workbenchApi.deleteProject(projectId);
      await hardRefresh();
    } catch (error) {
      setErrorText("删除项目失败：" + toErrorMessage(error));
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
          void syncStateOnly();
          void syncProjectsOnly();
          setTransientChat(null);
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
          void syncStateOnly();
          void syncProjectsOnly();
          setTransientChat(null);
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

  const resetProject = async () => {
    const yes = window.confirm(
      `要重置 ${projectName} 吗？\n\n这会清空当前项目的状态、工件和图片。`,
    );
    if (!yes) {
      return;
    }

    await workbenchApi.resetCurrentProject();
    setTransientChat(null);
    setFileCache({});
    setErrorText("");
    setWarningText("");
    await hardRefresh();
  };

  useEffect(() => {
    void hardRefresh().catch((error) => {
      setErrorText("加载失败：" + toErrorMessage(error));
    });
  }, []);

  useEffect(() => {
    if (!model.project_id) {
      return;
    }

    const source = workbenchApi.openProjectEvents(model.project_id, handleWorkbenchEvent);
    return () => {
      source.close();
    };
  }, [model.project_id]);

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

  return (
    <div className="app">
      <LeftSidebar
        sidebarMode={sidebarMode}
        projectName={projectName}
        activeProjectId={model.project_id}
        projects={model.active_projects}
        archivedProjects={model.archived_projects}
        files={model.files}
        currentView={currentView}
        onBack={() => setSidebarMode("projects")}
        onOpenHistory={() => setSidebarMode("history")}
        onRefresh={() => {
          void hardRefresh();
        }}
        onReset={() => {
          void resetProject();
        }}
        onOpenProject={(projectId) => {
          void openProject(projectId);
        }}
        onOpenFile={(fileId) => {
          void openFile(fileId);
        }}
        onCreateProject={createProject}
        onRenameProject={(projectId, displayName) => {
          void renameProject(projectId, displayName);
        }}
        onArchiveProject={(projectId) => {
          void archiveProject(projectId);
        }}
        onRestoreProject={(projectId) => {
          void restoreProject(projectId);
        }}
        onDeleteProject={(projectId) => {
          void deleteProject(projectId);
        }}
      />

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
      />

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
        onSelectAgent={(agent) => {
          setCurrentView({ type: "agent", id: agent });
        }}
        activeProject={activeProject}
      />
    </div>
  );
}
