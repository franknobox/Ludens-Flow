import { EngineMcpConsole, type EngineCapability } from "./EngineMcpConsole";
import { MCP_ICONS } from "./McpIcons";

const UNREAL_CAPABILITIES: EngineCapability[] = [
  {
    id: "engine_list_scene",
    displayId: "unreal.level.actors",
    label: "读取关卡 Actor",
    desc: "读取当前 Level 中 Actor 列表，或按名称查询 Actor 与属性。",
    level: "只读",
    risk: "safe",
  },
  {
    id: "engine_create_object",
    displayId: "unreal.actor.spawn",
    label: "生成 Actor",
    desc: "在当前 Level 中生成 StaticMeshActor、PointLight、CameraActor 或 Blueprint Actor。",
    level: "需权限",
    risk: "write",
  },
  {
    id: "engine_move_object",
    displayId: "unreal.actor.transform",
    label: "调整 Transform",
    desc: "修改 Actor 的位置、旋转、缩放，或设置明确指定的 Actor 属性。",
    level: "需权限",
    risk: "write",
  },
  {
    id: "engine_create_script",
    displayId: "unreal.blueprint.asset",
    label: "Blueprint / 输入映射",
    desc: "创建、编译 Blueprint，添加组件，或创建项目输入映射。",
    level: "需权限",
    risk: "write",
  },
  {
    id: "engine_save_scene",
    displayId: "unreal.level.save",
    label: "保存关卡",
    desc: "当前 unreal-mcp 仓库没有明确稳定的保存关卡工具，后续需要在底层 MCP 补齐。",
    level: "待补工具",
    risk: "write",
  },
  {
    id: "engine_read_console",
    displayId: "unreal.output_log.read",
    label: "读取 Output Log",
    desc: "当前 unreal-mcp 仓库没有明确稳定的日志读取工具，后续需要在底层 MCP 补齐。",
    level: "待补工具",
    risk: "safe",
  },
  {
    id: "engine_run_project",
    displayId: "unreal.pie.run",
    label: "运行 / PIE",
    desc: "当前 unreal-mcp 仓库没有明确稳定的 Play-In-Editor 工具，后续需要在底层 MCP 补齐。",
    level: "待补工具",
    risk: "write",
  },
];

const UNREAL_MAPPING_HINTS: Record<string, string[]> = {
  engine_list_scene: ["get_actors_in_level", "find_actors_by_name", "get_actor_properties"],
  engine_create_object: ["spawn_actor", "spawn_blueprint_actor"],
  engine_move_object: ["set_actor_transform", "set_actor_property"],
  engine_create_script: [
    "create_blueprint",
    "compile_blueprint",
    "add_component_to_blueprint",
    "set_blueprint_property",
    "create_input_mapping",
  ],
  engine_save_scene: [],
  engine_read_console: [],
  engine_run_project: [],
};

export function UnrealMcpPage() {
  return (
    <EngineMcpConsole
      engine="unreal"
      name="Unreal MCP"
      title="Unreal 控制台"
      color="#ffffff"
      setupHint="请先在设置页的“引擎连接”中添加 Unreal MCP，并确保 Unreal Editor 侧插件已启动。"
      icon={MCP_ICONS.ue}
      capabilities={UNREAL_CAPABILITIES}
      mappingHints={UNREAL_MAPPING_HINTS}
      emptyHelp="unreal-mcp 需要同时启动 Python MCP Server 和 Unreal Editor 插件；当前页面只会显示已加载工具和受控能力映射。"
    />
  );
}
