import { PHASE_LABEL } from "./constants";
import { LeftSidebar } from "./components/LeftSidebar";
import { MainPanel } from "./components/MainPanel";
import { ProjectToolbar } from "./components/ProjectToolbar";
import { RightSidebar } from "./components/RightSidebar";
import { useWorkbenchController } from "./hooks/useWorkbenchController";
import { projectUpdated } from "./utils";
import "./styles/workbench.css";

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
    fastDevProgress,
    historyByAgent,
    mcpMode,
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
    setMcpMode,
    createProject,
    handleArchiveProject,
    handleRenameProject,
    openAigc,
    openCopywriting,
    openFile,
    openGameModel,
    openGithub,
    openMcp,
    openSkills,
    openProject,
    importGddFastDev,
    closeFastDevProgress,
    saveWorkspaceFile,
    selectAgent,
    sendAction,
    sendMessage,
    uploadWorkspaceFileAsset,
  } = controller;

  const phaseLabel = PHASE_LABEL[model.phase] || model.phase || "-";
  const engineLabel = engineStatusLabel(activeProject?.target_engine);

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
          onOpenCopywriting={openCopywriting}
          onOpenGameModel={openGameModel}
          onOpenSkills={openSkills}
          onOpenMcp={openMcp}
        />

        <MainPanel
          currentView={currentView}
          currentProjectId={model.project_id}
          currentAgent={model.current_agent}
          projectName={projectName}
          gameTags={activeProject?.game_tags || []}
          readOnly={readOnly}
          subtitle={subtitle}
          title={title}
          historyByAgent={historyByAgent}
          transientChat={transientChat}
          actions={model.actions}
          requestInFlight={requestInFlight}
          mcpMode={mcpMode}
          fileItems={model.files}
          fileCache={fileCache}
          fastDevProgress={fastDevProgress}
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
          onToggleMcpMode={setMcpMode}
          onSaveFile={async (fileId, content) => {
            await saveWorkspaceFile(fileId, content);
          }}
          onUploadFileAsset={uploadWorkspaceFileAsset}
          onImportGddFastDev={importGddFastDev}
          onCloseFastDevProgress={closeFastDevProgress}
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
        engineLabel={engineLabel}
        statusNote={statusNote}
        activeProject={activeProject}
        onSelectAgent={selectAgent}
      />
    </div>
  );
}

function engineStatusLabel(targetEngine?: string): string {
  switch ((targetEngine || "").toLowerCase()) {
    case "unity":
      return "Unity";
    case "godot":
      return "Godot";
    case "unreal":
      return "Unreal Engine";
    case "generic":
      return "通用";
    default:
      return "通用";
  }
}
