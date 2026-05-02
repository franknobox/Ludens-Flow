import { EngineMcpConsole, type EngineCapability } from "./EngineMcpConsole";
import { MCP_ICONS } from "./McpIcons";

const UNITY_CAPABILITIES: EngineCapability[] = [
  {
    id: "engine_list_scene",
    label: "读取场景结构",
    desc: "读取当前 Scene / Hierarchy，用于理解场景对象关系。",
    level: "只读",
    risk: "safe",
  },
  {
    id: "engine_read_console",
    label: "读取 Console",
    desc: "读取 Unity Console 日志、报错和警告，辅助定位问题。",
    level: "只读",
    risk: "safe",
  },
  {
    id: "engine_create_script",
    label: "创建脚本",
    desc: "在受控路径内创建 C# 脚本。",
    level: "需权限",
    risk: "write",
  },
  {
    id: "engine_create_object",
    label: "创建对象",
    desc: "创建 GameObject 或放置 Prefab。",
    level: "需权限",
    risk: "write",
  },
  {
    id: "engine_move_object",
    label: "移动对象",
    desc: "调整 GameObject 的 Transform。",
    level: "需权限",
    risk: "write",
  },
  {
    id: "engine_save_scene",
    label: "保存场景",
    desc: "保存当前或指定 Scene。",
    level: "需权限",
    risk: "write",
  },
  {
    id: "engine_run_project",
    label: "运行项目",
    desc: "进入 Play Mode 或执行测试 / 运行动作。",
    level: "需权限",
    risk: "write",
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

export function UnityMcpPage() {
  return (
    <EngineMcpConsole
      engine="unity"
      name="Unity MCP"
      title="Unity 控制台"
      color="#ffffff"
      setupHint="请先在设置页的“引擎连接”中添加 Unity MCP。"
      icon={MCP_ICONS.unity}
      capabilities={UNITY_CAPABILITIES}
      mappingHints={UNITY_MAPPING_HINTS}
    />
  );
}
