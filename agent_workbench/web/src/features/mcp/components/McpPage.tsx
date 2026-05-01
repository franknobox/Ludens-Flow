import type { McpTool } from "../../workbench/types";
import { BlenderMcpPage } from "./BlenderMcpPage";
import { GodotMcpPage } from "./GodotMcpPage";
import { UnityMcpPage } from "./UnityMcpPage";
import { UnrealMcpPage } from "./UnrealMcpPage";

interface McpPageProps {
  tool: McpTool;
}

export function McpPage({ tool }: McpPageProps) {
  if (tool === "unity") return <UnityMcpPage />;
  if (tool === "blender") return <BlenderMcpPage />;
  if (tool === "godot") return <GodotMcpPage />;
  return <UnrealMcpPage />;
}
