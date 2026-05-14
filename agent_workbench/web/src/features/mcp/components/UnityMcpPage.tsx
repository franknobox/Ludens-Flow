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
    desc: "在受控 Assets 路径内创建 C# 脚本。",
    level: "需权限",
    risk: "write",
  },
  {
    id: "engine_create_object",
    label: "创建对象",
    desc: "创建 GameObject、基础 Primitive 或放置 Prefab。",
    level: "需权限",
    risk: "write",
  },
  {
    id: "engine_move_object",
    label: "调整 Transform",
    desc: "修改 GameObject 的 Transform、父级、Tag、Layer 或组件。",
    level: "需权限",
    risk: "write",
  },
  {
    id: "engine_save_scene",
    label: "保存场景",
    desc: "保存当前 Scene，或保存到受控 Assets 路径。",
    level: "需权限",
    risk: "write",
  },
  {
    id: "engine_run_project",
    label: "运行 / 测试",
    desc: "进入 Play Mode、暂停、停止，或执行 Unity 测试。",
    level: "需权限",
    risk: "write",
  },
];

const UNITY_MAPPING_HINTS: Record<string, string[]> = {
  engine_list_scene: ["manage_scene"],
  engine_read_console: ["read_console"],
  engine_create_script: ["create_script", "manage_script"],
  engine_create_object: ["manage_gameobject"],
  engine_move_object: ["manage_gameobject"],
  engine_save_scene: ["manage_scene"],
  engine_run_project: ["manage_editor", "run_tests"],
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
