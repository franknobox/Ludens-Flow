import { useEffect, useMemo, useState } from "react";

import { workbenchApi } from "../workbench/api";
import { ProjectToolbar } from "../workbench/components/ProjectToolbar";
import { PHASE_LABEL } from "../workbench/constants";
import { useProjectRuntime } from "../workbench/state/ProjectRuntimeContext";
import { projectUpdated, toErrorMessage } from "../workbench/utils";
import type {
  ProjectMeta,
  ModelProfileSummary,
  ProjectSettingsResponse,
  ProjectWorkspace,
  ToolCatalogItem,
} from "../workbench/types";
import {
  GeneralSettingsSection,
  HistorySection,
  ToolsSection,
  WorkspacesSection,
} from "./sections/SettingsSections";

const SETTINGS_SECTIONS = [
  { id: "general", label: "通用设置", hint: "写入总开关" },
  { id: "tools", label: "工具", hint: "能力目录" },
  { id: "workspaces", label: "工作区清单", hint: "目录与权限" },
  { id: "history", label: "历史项目", hint: "归档与恢复" },
] as const;

type SettingsSectionId = (typeof SETTINGS_SECTIONS)[number]["id"];

interface SettingsPageProps {
  isActive?: boolean;
}

function normalizeWorkspacePathInput(value: string): string {
  const trimmed = value.trim();
  if (
    trimmed.length >= 2 &&
    trimmed[0] === trimmed[trimmed.length - 1] &&
    (trimmed[0] === '"' || trimmed[0] === "'")
  ) {
    return trimmed.slice(1, -1).trim();
  }
  return trimmed;
}

export function SettingsPage({ isActive = false }: SettingsPageProps) {
  const {
    runtimeState,
    projects,
    activeProjects,
    archivedProjects,
    refreshRuntime,
    selectProject,
    createProject: createRuntimeProject,
  } = useProjectRuntime();

  const [workspaces, setWorkspaces] = useState<ProjectWorkspace[]>([]);
  const [tools, setTools] = useState<ToolCatalogItem[]>([]);
  const [modelProfiles, setModelProfiles] = useState<ModelProfileSummary[]>([]);
  const [projectSettings, setProjectSettings] =
    useState<ProjectSettingsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [settingsSubmitting, setSettingsSubmitting] = useState(false);
  const [errorText, setErrorText] = useState("");
  const [successText, setSuccessText] = useState("");
  const [activeSection, setActiveSection] =
    useState<SettingsSectionId>("general");
  const [labelInput, setLabelInput] = useState("");
  const [kindInput, setKindInput] = useState("unity");
  const [pathInput, setPathInput] = useState("");
  const [writableInput, setWritableInput] = useState(false);
  const [topbarSlot, setTopbarSlot] = useState<HTMLElement | null>(null);
  const [modelRoutingDraft, setModelRoutingDraft] = useState("{}");
  const [modelRoutingDirty, setModelRoutingDirty] = useState(false);
  const [modelRoutingProjectId, setModelRoutingProjectId] = useState("");
  const [theme, setTheme] = useState(
    () => document.documentElement.getAttribute("data-theme") || "light",
  );

  const activeProject = useMemo(
    () => projects.find((project) => project.id === runtimeState?.project_id),
    [projects, runtimeState?.project_id],
  );

  const toolsByCategory = useMemo(
    () =>
      tools.reduce<Record<string, ToolCatalogItem[]>>((acc, tool) => {
        const key = tool.category || "general";
        if (!acc[key]) acc[key] = [];
        acc[key]!.push(tool);
        return acc;
      }, {}),
    [tools],
  );

  const phaseLabel =
    PHASE_LABEL[runtimeState?.phase || ""] || runtimeState?.phase || "未开始";
  const currentProjectName =
    activeProject?.display_name || activeProject?.title || "未选择项目";

  const clearMessages = () => {
    setErrorText("");
    setSuccessText("");
  };

  const modelRoutingValidation = useMemo(() => {
    const raw = modelRoutingDraft.trim();
    if (!raw) {
      return {
        parsed: {},
        normalized: "{}",
        error: "",
      } as const;
    }

    try {
      const parsed = JSON.parse(raw) as unknown;
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
        return {
          parsed: null,
          normalized: "",
          error: "模型路由必须是 JSON 对象，不能是数组或基础类型。",
        } as const;
      }

      return {
        parsed: parsed as Record<string, unknown>,
        normalized: JSON.stringify(parsed),
        error: "",
      } as const;
    } catch (error) {
      return {
        parsed: null,
        normalized: "",
        error: `JSON 格式错误：${toErrorMessage(error)}`,
      } as const;
    }
  }, [modelRoutingDraft]);

  const refresh = async () => {
    setLoading(true);
    setErrorText("");
    try {
      await refreshRuntime();

      const [workspacesResult, toolsResult, projectSettingsResult, modelProfilesResult] =
        await Promise.allSettled([
          workbenchApi.getCurrentWorkspaces(),
          workbenchApi.getTools(),
          workbenchApi.getCurrentProjectSettings(),
          workbenchApi.getModelProfiles(),
        ]);

      setWorkspaces(
        workspacesResult.status === "fulfilled"
          ? workspacesResult.value.workspaces || []
          : [],
      );
      setTools(
        toolsResult.status === "fulfilled" ? toolsResult.value.tools || [] : [],
      );
      setProjectSettings(
        projectSettingsResult.status === "fulfilled"
          ? projectSettingsResult.value
          : {
              project_id: runtimeState?.project_id || "",
              agent_file_write_enabled: true,
              agent_file_write_confirm_required: false,
            },
      );
      setModelProfiles(
        modelProfilesResult.status === "fulfilled"
          ? modelProfilesResult.value.profiles || []
          : [],
      );
    } catch (error) {
      setErrorText(toErrorMessage(error));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    setTopbarSlot(document.getElementById("topbar-center-slot"));
  }, []);

  useEffect(() => {
    void refresh();
  }, []);

  useEffect(() => {
    if (!isActive) return;
    void refresh();
  }, [isActive]);

  useEffect(() => {
    if (!projectSettings) return;

    const sourceProjectId = projectSettings.project_id || "";
    const sourceDraft = JSON.stringify(
      projectSettings.model_routing || {},
      null,
      2,
    );

    const switchedProject = modelRoutingProjectId !== sourceProjectId;
    if (switchedProject || !modelRoutingDirty) {
      setModelRoutingDraft(sourceDraft);
      setModelRoutingDirty(false);
      setModelRoutingProjectId(sourceProjectId);
    }
  }, [projectSettings, modelRoutingDirty, modelRoutingProjectId]);

  const openProject = async (projectId: string) => {
    if (!projectId) return;
    clearMessages();
    try {
      await selectProject(projectId);
      void refresh();
    } catch (error) {
      setErrorText(toErrorMessage(error));
    }
  };

  const createProject = async (title: string) => {
    const trimmed = title.trim();
    if (!trimmed) {
      setErrorText("请输入项目名称。");
      return false;
    }
    clearMessages();
    try {
      await createRuntimeProject(trimmed);
      void refresh();
      return true;
    } catch (error) {
      setErrorText(toErrorMessage(error));
      return false;
    }
  };

  const handleAddWorkspace = async () => {
    const root = normalizeWorkspacePathInput(pathInput);
    if (!root) {
      setErrorText("请先输入工作区目录路径。");
      setActiveSection("workspaces");
      return;
    }

    setSubmitting(true);
    clearMessages();
    try {
      const response = await workbenchApi.addCurrentWorkspace({
        root,
        kind: kindInput,
        label: labelInput.trim() || null,
        writable: writableInput,
        enabled: true,
      });
      setWorkspaces(response.workspaces || []);
      setLabelInput("");
      setPathInput("");
      setWritableInput(false);
      setSuccessText("工作区已加入当前项目。");
      setActiveSection("workspaces");
    } catch (error) {
      setErrorText(toErrorMessage(error));
      setActiveSection("workspaces");
    } finally {
      setSubmitting(false);
    }
  };

  const handleRemoveWorkspace = async (workspace: ProjectWorkspace) => {
    const confirmed = window.confirm(
      `要将“${workspace.label}”从当前项目的工作区清单中移除吗？\n\n这不会删除本地目录，只会移出允许访问列表。`,
    );
    if (!confirmed) return;

    clearMessages();
    try {
      const response = await workbenchApi.deleteCurrentWorkspace(workspace.id);
      setWorkspaces(response.workspaces || []);
      setSuccessText("工作区已移除。");
    } catch (error) {
      setErrorText(toErrorMessage(error));
    }
  };

  const handleRestoreProject = async (project: ProjectMeta) => {
    const confirmed = window.confirm(
      `要恢复“${project.display_name || project.id}”吗？\n\n恢复后它会重新出现在当前项目列表中。`,
    );
    if (!confirmed) return;

    clearMessages();
    try {
      await workbenchApi.restoreProject(project.id, false);
      setSuccessText("项目已恢复。");
      await refresh();
    } catch (error) {
      setErrorText(toErrorMessage(error));
    }
  };

  const handleDeleteProject = async (project: ProjectMeta) => {
    const confirmed = window.confirm(
      `要永久删除“${project.display_name || project.id}”吗？\n\n这会删除该项目的目录和数据，而且无法撤销。`,
    );
    if (!confirmed) return;

    clearMessages();
    try {
      await workbenchApi.deleteProject(project.id);
      setSuccessText("项目已删除。");
      await refresh();
    } catch (error) {
      setErrorText(toErrorMessage(error));
    }
  };

  const handleToggleFileWrite = async (enabled: boolean) => {
    setSettingsSubmitting(true);
    clearMessages();
    try {
      const response = await workbenchApi.updateCurrentProjectSettings({
        agent_file_write_enabled: enabled,
      });
      setProjectSettings(response);
      setSuccessText(
        enabled ? "已开启 Agent 文件写入。" : "已关闭 Agent 文件写入。",
      );
    } catch (error) {
      setErrorText(toErrorMessage(error));
    } finally {
      setSettingsSubmitting(false);
    }
  };

  const handleToggleFileWriteConfirm = async (required: boolean) => {
    setSettingsSubmitting(true);
    clearMessages();
    try {
      const response = await workbenchApi.updateCurrentProjectSettings({
        agent_file_write_confirm_required: required,
      });
      setProjectSettings(response);
      setSuccessText(
        required ? "已开启写入前确认。" : "已关闭写入前确认。",
      );
    } catch (error) {
      setErrorText(toErrorMessage(error));
    } finally {
      setSettingsSubmitting(false);
    }
  };

  const handleSaveModelRouting = async () => {
    if (modelRoutingValidation.error || !modelRoutingValidation.parsed) {
      setErrorText(modelRoutingValidation.error || "模型路由配置无效。");
      setActiveSection("general");
      return;
    }

    setSettingsSubmitting(true);
    clearMessages();
    try {
      const response = await workbenchApi.updateCurrentProjectSettings({
        model_routing: modelRoutingValidation.parsed,
      });
      setProjectSettings(response);
      setModelRoutingDraft(
        JSON.stringify(response.model_routing || {}, null, 2),
      );
      setModelRoutingDirty(false);
      setSuccessText("模型路由已保存。新请求会按新路由生效。");
    } catch (error) {
      setErrorText(toErrorMessage(error));
    } finally {
      setSettingsSubmitting(false);
    }
  };

  const handleThemeChange = (nextTheme: string) => {
    setTheme(nextTheme);
    document.documentElement.setAttribute("data-theme", nextTheme);
    localStorage.setItem("ludens_theme", nextTheme);
  };

  return (
    <>
      <ProjectToolbar
        isActive={isActive}
        mountNode={topbarSlot}
        projectName={currentProjectName}
        phaseLabel={phaseLabel}
        updatedLabel={projectUpdated(activeProject)}
        activeProjects={activeProjects}
        activeProjectId={runtimeState?.project_id}
        currentPhase={runtimeState?.phase}
        onSelectProject={openProject}
        onCreateProject={createProject}
      />

      <div className="settings-page">
        <aside className="settings-sidebar">
          <nav className="settings-nav" aria-label="设置目录">
            {SETTINGS_SECTIONS.map((section) => {
              const isCurrent = activeSection === section.id;
              return (
                <button
                  key={section.id}
                  type="button"
                  className={`settings-nav-item${isCurrent ? " is-active" : ""}`}
                  onClick={() => {
                    clearMessages();
                    setActiveSection(section.id);
                  }}
                >
                  <span className="settings-nav-label">{section.label}</span>
                  <span className="settings-nav-text">{section.hint}</span>
                </button>
              );
            })}
          </nav>
        </aside>

        <main className="settings-detail">
          {activeSection === "general" ? (
            <GeneralSettingsSection
              projectSettings={projectSettings}
              loading={loading}
              settingsSubmitting={settingsSubmitting}
              modelProfiles={modelProfiles}
              theme={theme}
              modelRoutingDraft={modelRoutingDraft}
              modelRoutingDirty={modelRoutingDirty}
              modelRoutingValidation={modelRoutingValidation}
              onToggleFileWrite={(enabled) => {
                void handleToggleFileWrite(enabled);
              }}
              onToggleFileWriteConfirm={(required) => {
                void handleToggleFileWriteConfirm(required);
              }}
              onThemeChange={handleThemeChange}
              onModelRoutingDraftChange={(value) => {
                setModelRoutingDraft(value);
                setModelRoutingDirty(true);
              }}
              onClearModelRouting={() => {
                setModelRoutingDraft("{}");
                setModelRoutingDirty(true);
                clearMessages();
              }}
              onSaveModelRouting={() => {
                void handleSaveModelRouting();
              }}
            />
          ) : null}
          {activeSection === "tools" ? (
            <ToolsSection tools={tools} toolsByCategory={toolsByCategory} />
          ) : null}
          {activeSection === "workspaces" ? (
            <WorkspacesSection
              loading={loading}
              submitting={submitting}
              workspaces={workspaces}
              labelInput={labelInput}
              kindInput={kindInput}
              pathInput={pathInput}
              writableInput={writableInput}
              onLabelChange={setLabelInput}
              onKindChange={setKindInput}
              onPathChange={setPathInput}
              onWritableChange={setWritableInput}
              onAddWorkspace={() => {
                void handleAddWorkspace();
              }}
              onRemoveWorkspace={(workspace) => {
                void handleRemoveWorkspace(workspace);
              }}
            />
          ) : null}
          {activeSection === "history" ? (
            <HistorySection
              archivedProjects={archivedProjects}
              projectUpdated={projectUpdated}
              onRestoreProject={(project) => {
                void handleRestoreProject(project);
              }}
              onDeleteProject={(project) => {
                void handleDeleteProject(project);
              }}
            />
          ) : null}
          {successText ? (
            <div className="settings-feedback success">{successText}</div>
          ) : null}
          {errorText ? (
            <div className="settings-feedback error">{errorText}</div>
          ) : null}
        </main>
      </div>
    </>
  );
}
