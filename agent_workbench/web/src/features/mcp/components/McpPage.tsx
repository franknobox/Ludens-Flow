import { useEffect, useMemo, useState } from "react";

import { workbenchApi } from "../../workbench/api";
import type { McpConnectionConfig, McpConnectionStatus, McpTool } from "../../workbench/types";
import { MCP_ICONS } from "./McpIcons";

const MCP_META: Record<McpTool, { name: string; desc: string; color: string }> = {
  unity: {
    name: "Unity MCP",
    desc: "连接 Unity Editor 侧 MCP 工具，用于读取场景、查看 Console、创建脚本和执行受控编辑器操作。",
    color: "#ffffff",
  },
  godot: {
    name: "Godot MCP",
    desc: "面向 Godot 项目的 MCP 连接入口，后续用于节点树、脚本和运行状态协作。",
    color: "#478cbf",
  },
  ue: {
    name: "Unreal Engine MCP",
    desc: "面向 Unreal 项目的 MCP 连接入口，后续用于关卡对象、日志和运行状态协作。",
    color: "#ffffff",
  },
  blender: {
    name: "Blender MCP",
    desc: "面向 Blender 的 MCP 连接入口，后续用于场景对象、建模脚本和资产生成协作。",
    color: "#e87d0d",
  },
};

const UNITY_CAPABILITIES = [
  {
    id: "engine_list_scene",
    label: "读取场景结构",
    desc: "读取当前 Scene / Hierarchy，用于理解场景对象关系。",
    level: "只读",
  },
  {
    id: "engine_read_console",
    label: "读取 Console",
    desc: "读取 Unity Console 日志、报错和警告，辅助定位问题。",
    level: "只读",
  },
  {
    id: "engine_create_script",
    label: "创建脚本",
    desc: "在受控路径内创建 C# 脚本。",
    level: "需权限",
  },
  {
    id: "engine_create_object",
    label: "创建对象",
    desc: "创建 GameObject 或放置 Prefab。",
    level: "需权限",
  },
  {
    id: "engine_move_object",
    label: "移动对象",
    desc: "调整 GameObject 的 Transform。",
    level: "需权限",
  },
  {
    id: "engine_save_scene",
    label: "保存场景",
    desc: "保存当前或指定 Scene。",
    level: "需权限",
  },
  {
    id: "engine_run_project",
    label: "运行项目",
    desc: "进入 Play Mode 或执行测试 / 运行动作。",
    level: "需权限",
  },
];

const UNITY_MAPPING_HINTS: Record<string, string[]> = {
  engine_list_scene: [
    "get_scene_hierarchy",
    "get_current_scene_hierarchy",
    "list_scene",
    "list_gameobjects",
    "get_hierarchy",
  ],
  engine_read_console: ["read_console", "get_console_logs", "get_logs", "get_log_entries"],
  engine_create_script: ["create_script", "create_csharp_script"],
  engine_create_object: ["create_gameobject", "create_object", "create_prefab", "add_gameobject"],
  engine_move_object: ["move_gameobject", "set_transform", "modify_gameobject", "update_transform"],
  engine_save_scene: ["save_scene", "save_current_scene"],
  engine_run_project: ["start_play_mode", "run_tests", "play_unity_game"],
};

function normalizeToolName(name: string): string {
  return name.toLowerCase().replace(/[^a-z0-9]/g, "");
}

function matchUnityTool(capabilityId: string, tools: McpConnectionStatus["tools"]): string {
  const names = tools.map((tool) => tool.name);
  const normalized = new Map(names.map((name) => [normalizeToolName(name), name]));
  for (const candidate of UNITY_MAPPING_HINTS[capabilityId] || []) {
    if (names.includes(candidate)) return candidate;
    const matched = normalized.get(normalizeToolName(candidate));
    if (matched) return matched;
  }
  return "";
}

function statusLabel(status?: McpConnectionStatus): string {
  if (!status) return "已配置";
  if (status.status === "not_configured") return "未配置";
  if (status.status === "configured") return "已配置";
  if (status.status === "reachable") return "可连接";
  if (status.status === "tools_loaded") return "工具已加载";
  return "连接失败";
}

function statusClass(status?: McpConnectionStatus): string {
  if (!status) return "neutral";
  if (status.status === "tools_loaded" || status.status === "reachable") return "ok";
  if (status.status === "failed") return "danger";
  if (status.status === "not_configured") return "muted";
  return "neutral";
}

export function McpPage({ tool }: McpPageProps) {
  const meta = MCP_META[tool];
  const Icon = MCP_ICONS[tool];
  const [connections, setConnections] = useState<McpConnectionConfig[]>([]);
  const [status, setStatus] = useState<McpConnectionStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [errorText, setErrorText] = useState("");

  const unityConnection = useMemo(
    () => connections.find((connection) => connection.engine === "unity"),
    [connections],
  );

  const loadUnity = async (check = false) => {
    if (tool !== "unity") return;
    setLoading(true);
    setErrorText("");
    try {
      const settings = await workbenchApi.getCurrentProjectSettings();
      const nextConnections = settings.mcp_connections || [];
      setConnections(nextConnections);
      const unity = nextConnections.find((connection) => connection.engine === "unity");
      if (!unity) {
        setStatus(null);
        return;
      }
      if (check) {
        const result = await workbenchApi.checkCurrentMcpConnections({
          connection_id: unity.id,
        });
        setStatus(result.connections[0] || null);
        return;
      }
      setStatus({
        id: unity.id,
        engine: unity.engine,
        label: unity.label,
        enabled: unity.enabled,
        configured: Boolean(unity.command),
        status: unity.command ? "configured" : "not_configured",
        message: "",
        tools: [],
        tool_count: 0,
      });
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : String(error));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadUnity(false);
  }, [tool]);

  if (tool === "unity") {
    const tools = status?.tools || [];
    const mappedCount = UNITY_CAPABILITIES.filter((capability) =>
      matchUnityTool(capability.id, tools),
    ).length;

    return (
      <div className="mcp-console-page unity-mcp-page">
        <section className="mcp-console-hero">
          <div className="mcp-console-title-row">
            <div className="mcp-console-icon" style={{ color: meta.color }}>
              <Icon size={34} />
            </div>
            <div>
              <div className="mcp-console-kicker">ENGINE MCP</div>
              <h1>Unity 控制台</h1>
            </div>
          </div>
          <div className="mcp-hero-status" aria-label="Unity MCP 连接摘要">
            <div>
              <span>配置</span>
              <strong>{unityConnection?.label || "未配置"}</strong>
            </div>
            <div>
              <span>命令</span>
              <code>{unityConnection?.command || "-"}</code>
            </div>
            <div>
              <span>工具</span>
              <strong>{status?.tool_count || 0}</strong>
            </div>
          </div>
          <div className="mcp-console-actions">
            <span className={`mcp-status-chip ${statusClass(status || undefined)}`}>
              {unityConnection ? statusLabel(status || undefined) : "未配置"}
            </span>
            <button
              type="button"
              className="mcp-console-button"
              disabled={loading || !unityConnection}
              onClick={() => {
                void loadUnity(true);
              }}
            >
              {loading ? "检查中..." : "重新检查"}
            </button>
          </div>
        </section>

        <div className="mcp-console-grid">
          <section className="mcp-panel mcp-panel-capabilities">
            <div className="mcp-panel-head">
              <h2>能力名单</h2>
              <span>{mappedCount} / {UNITY_CAPABILITIES.length}</span>
            </div>
            <div className="mcp-capability-list">
              {UNITY_CAPABILITIES.map((capability) => {
                const mappedTool = matchUnityTool(capability.id, tools);
                return (
                  <article
                    key={capability.id}
                    className="mcp-capability-card"
                    title={capability.desc}
                  >
                    <div>
                      <h3>{capability.label}</h3>
                      <code>{capability.id}</code>
                    </div>
                    <div className="mcp-capability-map">
                      <span>映射</span>
                      <strong>{mappedTool || "未匹配到底层 MCP 工具"}</strong>
                    </div>
                    <div className="mcp-card-footer">
                      <span className="mcp-mini-chip">{capability.level}</span>
                      <span
                        className={`mcp-mini-chip ${
                          mappedTool ? "ok" : tools.length ? "danger" : "muted"
                        }`}
                      >
                        {mappedTool ? "已匹配" : tools.length ? "未匹配" : "待检查"}
                      </span>
                    </div>
                  </article>
                );
              })}
            </div>
          </section>

          <section className="mcp-panel mcp-panel-log">
            <div className="mcp-panel-head">
              <h2>最近检查结果</h2>
              <span>{tools.length} tools</span>
            </div>
            {!unityConnection ? (
              <div className="mcp-empty">请先在设置页的“引擎连接”中添加 Unity MCP。</div>
            ) : !tools.length ? (
              <div className="mcp-empty">
                尚未读取到底层工具列表。点击“重新检查”后会显示 MCP 返回的工具。
                {status?.message ? <p>{status.message}</p> : null}
                {errorText ? <p className="danger">{errorText}</p> : null}
              </div>
            ) : (
              <div className="mcp-tool-list">
                {tools.map((item) => (
                  <article key={item.name}>
                    <strong>{item.name}</strong>
                    {item.description ? <p>{item.description}</p> : null}
                  </article>
                ))}
              </div>
            )}
          </section>

        </div>
      </div>
    );
  }

  return (
    <div className="mcp-placeholder">
      <div className="mcp-placeholder-icon-wrap" style={{ color: meta.color }}>
        <Icon size={56} />
      </div>
      <div className="mcp-placeholder-name">{meta.name}</div>
      <div className="mcp-placeholder-desc">{meta.desc}</div>
      <div className="mcp-placeholder-badge">即将上线 · Coming Soon</div>
    </div>
  );
}

interface McpPageProps {
  tool: McpTool;
}
