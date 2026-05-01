import type { McpTool } from "../../workbench/types";
import { MCP_ICONS } from "./McpIcons";

interface McpComingSoonPageProps {
  tool: McpTool;
  name: string;
  desc: string;
  color: string;
}

export function McpComingSoonPage({ tool, name, desc, color }: McpComingSoonPageProps) {
  const Icon = MCP_ICONS[tool];

  return (
    <div className="mcp-placeholder">
      <div className="mcp-placeholder-icon-wrap" style={{ color }}>
        <Icon size={56} />
      </div>
      <div className="mcp-placeholder-name">{name}</div>
      <div className="mcp-placeholder-desc">{desc}</div>
      <div className="mcp-placeholder-badge">即将上线 · Coming Soon</div>
    </div>
  );
}
