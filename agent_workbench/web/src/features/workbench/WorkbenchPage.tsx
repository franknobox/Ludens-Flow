import { PHASE_LABEL } from "./constants";
import { LeftSidebar } from "./components/LeftSidebar";
import { MainPanel } from "./components/MainPanel";
import { ProjectToolbar } from "./components/ProjectToolbar";
import { RightSidebar } from "./components/RightSidebar";
import { useWorkbenchController } from "./hooks/useWorkbenchController";
import { projectUpdated } from "./utils";

type WorkbenchPageProps = {
  isActive?: boolean;
};

export function WorkbenchPage({ isActive = false }: WorkbenchPageProps) {
  const controller = useWorkbenchController();
  const {
    activeProject,
    activeProjects,
    archiveSubmitting,
    contentAreaRef,
    currentView,
    errorText,
    fileCache,
    historyByAgent,
    model,
    projectName,
    readOnly,
    requestInFlight,
    statusNote,
    subtitle,
    title,
    topbarSlot,
    transientChat,
    warningText,
    createProject,
    handleArchiveProject,
    handleRenameProject,
    openAigc,
    openFile,
    openGameModel,
    openGithub,
    openMcp,
    openProject,
    saveWorkspaceFile,
    selectAgent,
    sendAction,
    sendMessage,
  } = controller;

  const phaseLabel = PHASE_LABEL[model.phase] || model.phase || "-";

  const modeBadge =
    currentView.type === "github"
      ? "GitHub 可视化"
      : currentView.type === "aigc"
      ? "AIGC 集成"
      : currentView.type === "game-model"
      ? "游戏内模型接入"
      : currentView.type === "mcp"
      ? "MCP 集成"
      : currentView.type === "agent"
      ? "Agent 对话"
      : "文件查看";

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
        <ProjectToolbar
          isActive={isActive}
          mountNode={topbarSlot}
          projectName={projectName}
          phaseLabel={phaseLabel}
          updatedLabel={projectUpdated(activeProject)}
          activeProjects={activeProjects}
          activeProjectId={model.project_id}
          currentPhase={model.phase}
          onSelectProject={openProject}
          onCreateProject={createProject}
          settings={{
            activeProject,
            archiveSubmitting,
            onRenameProject: handleRenameProject,
            onArchiveProject: handleArchiveProject,
          }}
          onOpenGithub={openGithub}
          onOpenAigc={openAigc}
          onOpenGameModel={openGameModel}
          onOpenMcp={openMcp}
        />

        <MainPanel
          currentView={currentView}
          currentProjectId={model.project_id}
          currentAgent={model.current_agent}
          projectName={projectName}
          phaseLabel={phaseLabel}
          modeBadge={modeBadge}
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
        phaseLabel={phaseLabel}
        iterationCount={model.iteration_count || 0}
        filesCount={model.files.length}
        modeLabel={readOnly ? "只读" : "可写"}
        statusUpdated={projectUpdated(activeProject)}
        statusLastPhase={activeProject?.last_phase || "-"}
        statusNote={statusNote}
        activeProject={activeProject}
        onSelectAgent={selectAgent}
      />
    </div>
  );
}