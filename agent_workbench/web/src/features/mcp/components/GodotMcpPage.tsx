import { EngineMcpConsole, type EngineCapability } from "./EngineMcpConsole";
import { MCP_ICONS } from "./McpIcons";

const GODOT_CAPABILITIES: EngineCapability[] = [
  {
    id: "engine_list_scene",
    label: "读取项目信息",
    desc: "读取 Godot 项目名称、版本、场景/脚本/资源数量等基础信息。",
    level: "只读",
    risk: "safe",
  },
  {
    id: "engine_read_console",
    label: "读取调试输出",
    desc: "读取当前运行中的 Godot 项目 stdout / stderr。",
    level: "只读",
    risk: "safe",
  },
  {
    id: "engine_create_object",
    label: "创建场景 / 节点",
    desc: "创建 .tscn 场景，或向已有场景添加 Node2D、Node3D、Sprite2D 等节点。",
    level: "需权限",
    risk: "write",
  },
  {
    id: "engine_save_scene",
    label: "保存场景",
    desc: "保存已有 Godot 场景，或另存为新的 .tscn / .scn。",
    level: "需权限",
    risk: "write",
  },
  {
    id: "engine_run_project",
    label: "运行 / 停止",
    desc: "启动 Godot Editor、运行项目或停止当前运行进程。",
    level: "需权限",
    risk: "write",
  },
  {
    id: "engine_move_object",
    label: "调整节点",
    desc: "预留给具备节点属性修改能力的 Godot MCP 工具。",
    level: "需权限",
    risk: "write",
  },
  {
    id: "engine_create_script",
    label: "创建脚本",
    desc: "预留给具备脚本写入能力的 Godot MCP 工具；当前可用工作区文件工具写入 .gd。",
    level: "需权限",
    risk: "write",
  },
];

const GODOT_MAPPING_HINTS: Record<string, string[]> = {
  engine_list_scene: ["get_project_info"],
  engine_read_console: ["get_debug_output"],
  engine_create_object: ["add_node", "create_scene"],
  engine_save_scene: ["save_scene"],
  engine_run_project: ["run_project", "launch_editor", "stop_project"],
  engine_move_object: ["set_node_properties", "update_node", "move_node"],
  engine_create_script: ["create_script", "create_gdscript"],
};

export function GodotMcpPage() {
  return (
    <EngineMcpConsole
      engine="godot"
      name="Godot MCP"
      title="Godot 控制台"
      color="#478cbf"
      setupHint="请先在设置页的“引擎连接”中添加 Godot MCP，并在工作区清单绑定 Godot 项目目录。"
      icon={MCP_ICONS.godot}
      capabilities={GODOT_CAPABILITIES}
      mappingHints={GODOT_MAPPING_HINTS}
    />
  );
}
