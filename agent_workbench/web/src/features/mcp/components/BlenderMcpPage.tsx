import { EngineMcpConsole, type EngineCapability } from "./EngineMcpConsole";
import { MCP_ICONS } from "./McpIcons";

const BLENDER_CAPABILITIES: EngineCapability[] = [
  {
    id: "engine_list_scene",
    label: "读取场景信息",
    desc: "读取当前 Blender 场景、对象列表、材质和层级信息。",
    level: "只读",
    risk: "safe",
  },
  {
    id: "engine_create_object",
    label: "创建 / 删除 / 修改对象",
    desc: "创建基础形体、调整对象属性，后续可扩展到删除与复杂修改。",
    level: "需权限",
    risk: "write",
  },
  {
    id: "engine_move_object",
    label: "调整 Transform",
    desc: "移动、旋转、缩放 Blender 对象。",
    level: "需权限",
    risk: "write",
  },
  {
    id: "engine_save_scene",
    label: "保存 .blend",
    desc: "保存当前 Blender 文件或指定文件。",
    level: "需权限",
    risk: "write",
  },
  {
    id: "engine_create_script",
    label: "执行 Blender Python",
    desc: "映射到 execute_blender_code / run_script 一类工具，能力强但风险最高。",
    level: "高风险",
    risk: "high",
  },
  {
    id: "engine_run_project",
    label: "渲染 / 运行任务",
    desc: "用于渲染场景或触发 Blender 侧自动化任务。",
    level: "需权限",
    risk: "write",
  },
];

const BLENDER_MAPPING_HINTS: Record<string, string[]> = {
  engine_list_scene: ["get_scene_info", "get_scene_objects", "get_object_info"],
  engine_create_object: ["create_object", "add_object", "delete_object", "modify_object"],
  engine_move_object: ["modify_object", "set_object_transform"],
  engine_save_scene: ["save_file", "save_blend_file"],
  engine_create_script: ["execute_blender_code", "run_script", "execute_blender_python"],
  engine_run_project: ["render_scene", "get_viewport_screenshot"],
};

export function BlenderMcpPage() {
  return (
    <EngineMcpConsole
      engine="blender"
      name="Blender MCP"
      title="Blender 控制台"
      color="#e87d0d"
      setupHint="请先在设置页的“引擎连接”中添加 Blender MCP，常用命令为 uvx blender-mcp。"
      icon={MCP_ICONS.blender}
      capabilities={BLENDER_CAPABILITIES}
      mappingHints={BLENDER_MAPPING_HINTS}
      emptyHelp="BlenderMCP 需要先在 Blender 中安装并启用 addon，然后点击侧栏里的连接按钮。"
    />
  );
}
