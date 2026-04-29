import type { McpTool } from "../../workbench/types";
import { MCP_ICONS } from "./McpIcons";

const MCP_META: Record<McpTool, { name: string; desc: string; color: string }> = {
  unity: {
    name: "Unity MCP",
    desc: "通过 Model Context Protocol 将 AI 能力直接接入 Unity 编辑器，实现场景生成、脚本辅助与资产管理。",
    color: "#ffffff",
  },
  godot: {
    name: "Godot MCP",
    desc: "面向 Godot 4 的 MCP 集成，支持 GDScript 生成、节点树操作与游戏逻辑辅助。",
    color: "#478cbf",
  },
  ue: {
    name: "Unreal Engine MCP",
    desc: "为 UE5 蓝图与 C++ 项目提供 AI 辅助，涵盖关卡设计、材质生成与 Nanite/Lumen 配置。",
    color: "#ffffff",
  },
  blender: {
    name: "Blender MCP",
    desc: "在 Blender 中通过 MCP 调用大模型，自动化建模、绑骨、渲染管线配置与 Python 脚本生成。",
    color: "#e87d0d",
  },
};

interface McpPageProps {
  tool: McpTool;
}

export function McpPage({ tool }: McpPageProps) {
  const meta = MCP_META[tool];
  const Icon = MCP_ICONS[tool];

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
