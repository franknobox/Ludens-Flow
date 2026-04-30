import { useEffect, useMemo, useState } from "react";

import { workbenchApi } from "../workbench/api";
import { ProjectToolbar } from "../workbench/components/ProjectToolbar";
import { PHASE_LABEL } from "../workbench/constants";
import { useProjectRuntime } from "../workbench/state/ProjectRuntimeContext";
import { projectUpdated, toErrorMessage } from "../workbench/utils";
import { SkillsSettingsSection } from "../skills/components/SkillsSettingsSection";
import type {
  ProjectMeta,
  McpConnectionConfig,
  McpConnectionStatus,
  ModelProfileSummary,
  ProjectSettingsResponse,
  ProjectWorkspace,
  ToolCatalogItem,
  UserProfileResponse,
} from "../workbench/types";
import {
  EngineConnectionsSection,
  GeneralSettingsSection,
  HistorySection,
  ToolsSection,
  UserProfileSection,
  WorkspacesSection,
} from "./sections/SettingsSections";

const SETTINGS_SECTIONS = [
  { id: "general", label: "通用设置", hint: "写入与模型" },
  { id: "profile", label: "用户画像", hint: "身份与偏好" },
  { id: "skills", label: "Skills", hint: "导入与管理" },
  { id: "tools", label: "工具", hint: "能力目录" },
  { id: "engines", label: "引擎连接", hint: "MCP 健康检查" },
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

function defaultMcpStatus(connection: McpConnectionConfig): McpConnectionStatus {
  return {
    id: connection.id,
    engine: connection.engine,
    label: connection.label,
    enabled: connection.enabled,
    configured: Boolean(connection.command.trim()),
    status: connection.command.trim() ? "configured" : "not_configured",
    message: connection.enabled ? "" : "Connection is disabled.",
    tools: [],
    tool_count: 0,
  };
}

function normalizeMcpConnections(value: unknown): McpConnectionConfig[] {
  if (!Array.isArray(value)) return [];
  return value
    .filter((item): item is McpConnectionConfig => {
      return Boolean(item && typeof item === "object" && "id" in item);
    })
    .map((item) => ({
      id: String(item.id || ""),
      engine: (item.engine || "unity") as McpConnectionConfig["engine"],
      label: String(item.label || item.id || "MCP Connection"),
      command: String(item.command || ""),
      args: Array.isArray(item.args) ? item.args.map((arg) => String(arg)) : [],
      env: item.env && typeof item.env === "object" ? item.env : {},
      enabled: item.enabled !== false,
    }));
}

function parseLines(value: string): string[] {
  return value
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
}

function parseEnvLines(value: string): Record<string, string> {
  const env: Record<string, string> = {};
  for (const line of parseLines(value)) {
    const [key, ...rest] = line.split("=");
    const name = key.trim();
    if (!name) continue;
    env[name] = rest.join("=").trim();
  }
  return env;
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
  const [mcpConnections, setMcpConnections] = useState<McpConnectionConfig[]>([]);
  const [mcpStatuses, setMcpStatuses] = useState<Record<string, McpConnectionStatus>>({});
  const [mcpChecking, setMcpChecking] = useState(false);
  const [modelProfiles, setModelProfiles] = useState<ModelProfileSummary[]>([]);
  const [projectSettings, setProjectSettings] =
    useState<ProjectSettingsResponse | null>(null);
  const [userProfile, setUserProfile] = useState<UserProfileResponse | null>(null);
  const [userProfileDraft, setUserProfileDraft] = useState("");
  const [userProfileDirty, setUserProfileDirty] = useState(false);
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
  const [mcpEngineInput, setMcpEngineInput] =
    useState<McpConnectionConfig["engine"]>("unity");
  const [mcpLabelInput, setMcpLabelInput] = useState("");
  const [mcpCommandInput, setMcpCommandInput] = useState("");
  const [mcpArgsInput, setMcpArgsInput] = useState("");
  const [mcpEnvInput, setMcpEnvInput] = useState("");
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

      const [
        workspacesResult,
        toolsResult,
        projectSettingsResult,
        modelProfilesResult,
        userProfileResult,
      ] =
        await Promise.allSettled([
          workbenchApi.getCurrentWorkspaces(),
          workbenchApi.getTools(),
          workbenchApi.getCurrentProjectSettings(),
          workbenchApi.getModelProfiles(),
          workbenchApi.getCurrentUserProfile(),
        ]);

      setWorkspaces(
        workspacesResult.status === "fulfilled"
          ? workspacesResult.value.workspaces || []
          : [],
      );
      setTools(
        toolsResult.status === "fulfilled" ? toolsResult.value.tools || [] : [],
      );
      const nextProjectSettings =
        projectSettingsResult.status === "fulfilled"
          ? projectSettingsResult.value
          : {
              project_id: runtimeState?.project_id || "",
              agent_file_write_enabled: true,
              agent_file_write_confirm_required: false,
              mcp_connections: [],
            };
      setProjectSettings(nextProjectSettings);
      const nextMcpConnections = normalizeMcpConnections(
        nextProjectSettings.mcp_connections,
      );
      setMcpConnections(nextMcpConnections);
      setMcpStatuses(
        Object.fromEntries(
          nextMcpConnections.map((connection) => [
            connection.id,
            defaultMcpStatus(connection),
          ]),
        ),
      );
      setModelProfiles(
        modelProfilesResult.status === "fulfilled"
          ? modelProfilesResult.value.profiles || []
          : [],
      );
      if (userProfileResult.status === "fulfilled") {
        setUserProfile(userProfileResult.value);
        setUserProfileDraft(userProfileResult.value.content || "");
        setUserProfileDirty(false);
      }
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

  const saveMcpConnections = async (connections: McpConnectionConfig[]) => {
    setSettingsSubmitting(true);
    clearMessages();
    try {
      const response = await workbenchApi.updateCurrentProjectSettings({
        mcp_connections: connections,
      });
      setProjectSettings(response);
      const normalized = normalizeMcpConnections(response.mcp_connections);
      setMcpConnections(normalized);
      setMcpStatuses((prev) => ({
        ...Object.fromEntries(
          normalized.map((connection) => [
            connection.id,
            prev[connection.id] || defaultMcpStatus(connection),
          ]),
        ),
      }));
      setSuccessText("引擎连接配置已保存。");
      setActiveSection("engines");
    } catch (error) {
      setErrorText(toErrorMessage(error));
      setActiveSection("engines");
    } finally {
      setSettingsSubmitting(false);
    }
  };

  const handleAddMcpConnection = async () => {
    const command = mcpCommandInput.trim();
    const engine = mcpEngineInput;
    const nextConnection: McpConnectionConfig = {
      id: `${engine}-mcp`,
      engine,
      label: mcpLabelInput.trim() || `${engine.toUpperCase()} MCP`,
      command,
      args: parseLines(mcpArgsInput),
      env: parseEnvLines(mcpEnvInput),
      enabled: true,
    };
    const nextConnections = [
      ...mcpConnections.filter((item) => item.id !== nextConnection.id),
      nextConnection,
    ];
    await saveMcpConnections(nextConnections);
    setMcpLabelInput("");
    setMcpCommandInput("");
    setMcpArgsInput("");
    setMcpEnvInput("");
  };

  const handleUpdateMcpConnection = async (
    connectionId: string,
    patch: Partial<McpConnectionConfig>,
  ) => {
    const nextConnections = mcpConnections.map((connection) =>
      connection.id === connectionId ? { ...connection, ...patch } : connection,
    );
    await saveMcpConnections(nextConnections);
  };

  const handleRemoveMcpConnection = async (connectionId: string) => {
    const target = mcpConnections.find((connection) => connection.id === connectionId);
    if (!target) return;
    if (!window.confirm(`要移除 ${target.label} 的 MCP 连接配置吗？`)) return;
    await saveMcpConnections(
      mcpConnections.filter((connection) => connection.id !== connectionId),
    );
  };

  const handleCheckMcpConnections = async (connectionId?: string) => {
    setMcpChecking(true);
    clearMessages();
    try {
      const response = await workbenchApi.checkCurrentMcpConnections({
        connection_id: connectionId || null,
      });
      setMcpStatuses((prev) => ({
        ...prev,
        ...Object.fromEntries(
          (response.connections || []).map((connection) => [
            connection.id,
            connection,
          ]),
        ),
      }));
      setSuccessText("MCP 健康检查已完成。");
      setActiveSection("engines");
    } catch (error) {
      setErrorText(toErrorMessage(error));
      setActiveSection("engines");
    } finally {
      setMcpChecking(false);
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

  const handleReloadUserProfile = async () => {
    clearMessages();
    try {
      const response = await workbenchApi.getCurrentUserProfile();
      setUserProfile(response);
      setUserProfileDraft(response.content || "");
      setUserProfileDirty(false);
      setSuccessText("用户画像已重新读取。");
    } catch (error) {
      setErrorText(toErrorMessage(error));
    }
  };

  const handleSaveUserProfile = async () => {
    setSettingsSubmitting(true);
    clearMessages();
    try {
      const response = await workbenchApi.updateCurrentUserProfile(userProfileDraft);
      setUserProfile(response);
      setUserProfileDraft(response.content || "");
      setUserProfileDirty(false);
      setSuccessText("用户画像已保存。新一轮 Agent 回复会读取更新后的画像。");
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
          {activeSection === "profile" ? (
            <UserProfileSection
              profile={userProfile}
              draft={userProfileDraft}
              dirty={userProfileDirty}
              loading={loading}
              submitting={settingsSubmitting}
              onDraftChange={(value) => {
                setUserProfileDraft(value);
                setUserProfileDirty(true);
              }}
              onReload={() => {
                void handleReloadUserProfile();
              }}
              onSave={() => {
                void handleSaveUserProfile();
              }}
            />
          ) : null}
          {activeSection === "tools" ? (
            <ToolsSection tools={tools} toolsByCategory={toolsByCategory} />
          ) : null}
          {activeSection === "skills" ? <SkillsSettingsSection /> : null}
          {activeSection === "engines" ? (
            <EngineConnectionsSection
              loading={loading}
              submitting={settingsSubmitting}
              checking={mcpChecking}
              connections={mcpConnections}
              statuses={mcpStatuses}
              engineInput={mcpEngineInput}
              labelInput={mcpLabelInput}
              commandInput={mcpCommandInput}
              argsInput={mcpArgsInput}
              envInput={mcpEnvInput}
              onEngineChange={setMcpEngineInput}
              onLabelChange={setMcpLabelInput}
              onCommandChange={setMcpCommandInput}
              onArgsChange={setMcpArgsInput}
              onEnvChange={setMcpEnvInput}
              onAddConnection={() => {
                void handleAddMcpConnection();
              }}
              onUpdateConnection={(connectionId, patch) => {
                void handleUpdateMcpConnection(connectionId, patch);
              }}
              onRemoveConnection={(connectionId) => {
                void handleRemoveMcpConnection(connectionId);
              }}
              onCheckConnection={(connectionId) => {
                void handleCheckMcpConnections(connectionId);
              }}
              onCheckAll={() => {
                void handleCheckMcpConnections();
              }}
            />
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
