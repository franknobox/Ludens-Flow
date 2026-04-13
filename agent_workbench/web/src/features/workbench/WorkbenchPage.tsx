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
  StateResponse,
  TransientChat,
  ViewState,
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

export function WorkbenchPage() {
  const [model, setModel] = useState<WorkbenchStateModel>(INITIAL_MODEL);
  const [currentView, setCurrentView] = useState<ViewState>({ type: "agent", id: "design" });
  const [sidebarMode, setSidebarMode] = useState<"projects" | "project">("projects");
  const [fileCache, setFileCache] = useState<Record<string, string>>({});
  const [requestInFlight, setRequestInFlight] = useState(false);
  const [transientChat, setTransientChat] = useState<TransientChat | null>(null);
  const [errorText, setErrorText] = useState("");

  const contentAreaRef = useRef<HTMLElement>(null);

  const historyByAgent = useMemo(() => buildHistoryByAgent(model), [model]);
  const activeProject = useMemo(
    () => model.projects.find((project) => project.id === model.project_id),
    [model.project_id, model.projects],
  );
  const projectName = activeProject?.display_name || model.project_id || "Project";

  const readOnly =
    currentView.type !== "agent" || currentView.id !== model.current_agent;

  const statusNote = useMemo(() => {
    if (activeProject?.archived) {
      return "Current project is archived. You can still inspect its local state and artifacts.";
    }
    if (model.artifact_frozen) {
      return "Current project is in DEV_COACHING. Canonical artifacts are frozen.";
    }
    if (activeProject?.last_message_preview) {
      return activeProject.last_message_preview;
    }
    return "Current project is writable. State, artifacts, profile and logs stay inside this project.";
  }, [activeProject, model.artifact_frozen]);

  const syncStateOnly = async (): Promise<StateResponse> => {
    const state = await workbenchApi.getState();
    setModel((prev) => ({
      ...toModelState(state),
      projects: prev.projects,
      files: prev.files,
    }));
    return state;
  };

  const syncProjectsOnly = async () => {
    const data = await workbenchApi.getProjects();
    setModel((prev) => ({
      ...prev,
      projects: data.projects || [],
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
      files: files.files || [],
    }));
    setFileCache((prev) => {
      const validIds = new Set((files.files || []).map((item) => item.id));
      const next: Record<string, string> = {};
      Object.keys(prev).forEach((key) => {
        if (validIds.has(key)) {
          next[key] = prev[key];
        }
      });
      return next;
    });

    setCurrentView({
      type: "agent",
      id: state.current_agent || phaseToAgent(state.phase),
    });
  };

  const openProject = async (projectId: string) => {
    if (!projectId) return;
    setSidebarMode("project");
    if (projectId === model.project_id) {
      return;
    }

    setErrorText("");
    try {
      await workbenchApi.selectProject(projectId);
      await hardRefresh();
    } catch (error) {
      setErrorText("Switch project failed: " + toErrorMessage(error));
    }
  };

  const openFile = async (fileId: string) => {
    setCurrentView({ type: "file", id: fileId });

    if (Object.prototype.hasOwnProperty.call(fileCache, fileId)) {
      return;
    }

    try {
      const data = await workbenchApi.getWorkspaceFileContent(fileId);
      setFileCache((prev) => ({ ...prev, [fileId]: data.content || "" }));
    } catch (error) {
      setFileCache((prev) => ({ ...prev, [fileId]: `Load failed: ${toErrorMessage(error)}` }));
    }
  };

  const createProject = async (projectId: string, title: string): Promise<boolean> => {
    if (!projectId) {
      setErrorText("Project id is required.");
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
      setErrorText("Create project failed: " + toErrorMessage(error));
      return false;
    }
  };

  const sendMessage = async (text: string, images: string[]) => {
    if (!text && !images.length) {
      return;
    }

    setErrorText("");
    setRequestInFlight(true);
    setTransientChat({
      agentKey: model.current_agent,
      phase: model.phase,
      userText: transientMessageText(text, images.length),
      thinking: true,
    });

    try {
      const response = await workbenchApi.postChat({
        message: text,
        images: images.length ? images : undefined,
      });
      if (response.error) {
        setErrorText(response.error);
      }
      setModel((prev) => mergeChatResponse(prev, response));
      setTransientChat(null);
      setFileCache({});
      const nextState = await syncStateOnly();
      setCurrentView({
        type: "agent",
        id: nextState.current_agent || phaseToAgent(nextState.phase),
      });
      void syncProjectsOnly();
    } catch (error) {
      setTransientChat((prev) => (prev ? { ...prev, thinking: false } : prev));
      setErrorText("Request failed: " + toErrorMessage(error));
    } finally {
      setRequestInFlight(false);
    }
  };

  const sendAction = async (actionId: string) => {
    if (!actionId || requestInFlight || readOnly || currentView.type !== "agent") {
      return;
    }

    setErrorText("");
    setRequestInFlight(true);
    setTransientChat({
      agentKey: currentView.id,
      phase: model.phase,
      userText: `[ACTION] ${actionId}`,
      thinking: true,
    });

    try {
      const response = await workbenchApi.postAction(actionId);
      if (response.error) {
        setErrorText(response.error);
      }
      setModel((prev) => mergeChatResponse(prev, response));
      setTransientChat(null);
      setFileCache({});
      const nextState = await syncStateOnly();
      setCurrentView({
        type: "agent",
        id: nextState.current_agent || phaseToAgent(nextState.phase),
      });
      void syncProjectsOnly();
    } catch (error) {
      setTransientChat((prev) => (prev ? { ...prev, thinking: false } : prev));
      setErrorText("Action failed: " + toErrorMessage(error));
    } finally {
      setRequestInFlight(false);
    }
  };

  const resetProject = async () => {
    const yes = window.confirm(
      `Reset ${projectName}?\n\nThis clears the current project's state, artifacts, and images.`,
    );
    if (!yes) {
      return;
    }

    await workbenchApi.resetCurrentProject();
    setTransientChat(null);
    setFileCache({});
    setErrorText("");
    await hardRefresh();
  };

  useEffect(() => {
    void hardRefresh().catch((error) => {
      setErrorText("Load failed: " + toErrorMessage(error));
    });
  }, []);

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
      ? `Current project: ${projectName} · Active agent: ${agentName(model.current_agent)}`
      : `Viewing artifact inside ${projectName}`;

  return (
    <div className="app">
      <LeftSidebar
        sidebarMode={sidebarMode}
        projectName={projectName}
        activeProjectId={model.project_id}
        projects={model.projects}
        files={model.files}
        currentView={currentView}
        onBack={() => setSidebarMode("projects")}
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
      />

      <MainPanel
        currentView={currentView}
        currentAgent={model.current_agent}
        projectName={projectName}
        phaseLabel={PHASE_LABEL[model.phase] || model.phase || "-"}
        modeBadge={currentView.type === "agent" ? "Agent Chat" : "File Viewer"}
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
        contentAreaRef={contentAreaRef}
        onSend={async (message, images) => {
          if (currentView.type !== "agent" || readOnly || requestInFlight) {
            return;
          }
          await sendMessage(message, images);
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
        modeLabel={readOnly ? "Read-only view" : "Writable"}
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
