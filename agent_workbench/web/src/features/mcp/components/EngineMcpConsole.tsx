import { useEffect, useMemo, useState } from "react";

import { workbenchApi } from "../../workbench/api";
import type { McpConnectionConfig, McpConnectionStatus, McpEngine } from "../../workbench/types";

interface IconProps {
  size?: number;
  className?: string;
}

export interface EngineCapability {
  id: string;
  displayId?: string;
  label: string;
  desc: string;
  level: string;
  risk?: "safe" | "write" | "high";
}

interface EngineMcpConsoleProps {
  engine: McpEngine;
  name: string;
  title: string;
  color: string;
  setupHint: string;
  icon: (props: IconProps) => JSX.Element;
  capabilities: EngineCapability[];
  mappingHints: Record<string, string[]>;
  emptyHelp?: string;
}

function normalizeToolName(name: string): string {
  return name.toLowerCase().replace(/[^a-z0-9]/g, "");
}

function matchTool(
  capabilityId: string,
  tools: McpConnectionStatus["tools"],
  mappingHints: Record<string, string[]>,
): string {
  const names = tools.map((tool) => tool.name);
  const normalized = new Map(names.map((name) => [normalizeToolName(name), name]));
  for (const candidate of mappingHints[capabilityId] || []) {
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

export function EngineMcpConsole({
  engine,
  name,
  title,
  color,
  setupHint,
  icon: Icon,
  capabilities,
  mappingHints,
  emptyHelp,
}: EngineMcpConsoleProps) {
  const [connections, setConnections] = useState<McpConnectionConfig[]>([]);
  const [status, setStatus] = useState<McpConnectionStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [errorText, setErrorText] = useState("");

  const connection = useMemo(
    () => connections.find((item) => item.engine === engine),
    [connections, engine],
  );

  const loadEngine = async (check = false) => {
    setLoading(true);
    setErrorText("");
    try {
      const settings = await workbenchApi.getCurrentProjectSettings();
      const nextConnections = settings.mcp_connections || [];
      setConnections(nextConnections);
      const target = nextConnections.find((item) => item.engine === engine);
      if (!target) {
        setStatus(null);
        return;
      }
      if (check) {
        const result = await workbenchApi.checkCurrentMcpConnections({
          connection_id: target.id,
        });
        setStatus(result.connections[0] || null);
        return;
      }
      setStatus({
        id: target.id,
        engine: target.engine,
        label: target.label,
        enabled: target.enabled,
        configured: Boolean(target.command),
        status: target.command ? "configured" : "not_configured",
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
    void loadEngine(true);
  }, [engine]);

  const tools = status?.tools || [];
  const mappedCount = capabilities.filter((capability) =>
    matchTool(capability.id, tools, mappingHints),
  ).length;

  return (
    <div className={`mcp-console-page ${engine}-mcp-page`}>
      <section className="mcp-console-hero">
        <div className="mcp-console-title-row">
          <div className="mcp-console-icon" style={{ color }}>
            <Icon size={34} />
          </div>
          <div>
            <div className="mcp-console-kicker">ENGINE MCP</div>
            <h1>{title}</h1>
          </div>
        </div>
        <div className="mcp-hero-status" aria-label={`${name} 连接摘要`}>
          <div>
            <span>配置</span>
            <strong>{connection?.label || "未配置"}</strong>
          </div>
          <div>
            <span>命令</span>
            <code>{connection?.command || "-"}</code>
          </div>
          <div>
            <span>工具</span>
            <strong>{status?.tool_count || 0}</strong>
          </div>
        </div>
        <div className="mcp-console-actions">
          <span className={`mcp-status-chip ${statusClass(status || undefined)}`}>
            {connection ? statusLabel(status || undefined) : "未配置"}
          </span>
          <button
            type="button"
            className="mcp-console-button"
            disabled={loading || !connection}
            onClick={() => {
              void loadEngine(true);
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
            <span>
              {mappedCount} / {capabilities.length}
            </span>
          </div>
          <div className="mcp-capability-list">
            {capabilities.map((capability) => {
              const mappedTool = matchTool(capability.id, tools, mappingHints);
              return (
                <article
                  key={capability.id}
                  className="mcp-capability-card"
                  title={capability.desc}
                >
                  <div>
                    <h3>{capability.label}</h3>
                    <code>{capability.displayId || capability.id}</code>
                  </div>
                  <div className="mcp-capability-map">
                    <span>映射</span>
                    <strong>{mappedTool || "未匹配到底层 MCP 工具"}</strong>
                  </div>
                  <div className="mcp-card-footer">
                    <span
                      className={`mcp-mini-chip ${
                        capability.risk === "high"
                          ? "danger"
                          : capability.risk === "safe"
                            ? "ok"
                            : ""
                      }`}
                    >
                      {capability.level}
                    </span>
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
          {!connection ? (
            <div className="mcp-empty">{setupHint}</div>
          ) : !tools.length ? (
            <div className="mcp-empty">
              尚未读取到底层工具列表。点击“重新检查”后会显示 MCP 返回的工具。
              {status?.message ? <p>{status.message}</p> : null}
              {errorText ? <p className="danger">{errorText}</p> : null}
              {emptyHelp ? <p>{emptyHelp}</p> : null}
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
