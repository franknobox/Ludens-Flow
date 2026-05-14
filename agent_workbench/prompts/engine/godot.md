# Godot Prompt Fragment

- 默认按 Godot 项目思路落地，优先考虑 Scene Tree、Node、Signal、Resource、Autoload、`.tscn` / `.tres` 和 `res://` 路径。
- 工程建议应兼顾 Godot 4.x、GDScript、节点组合、信号解耦、输入映射、场景实例化和运行调试输出。
- 文件建议以 Godot 项目根和 `res://` 为边界；不要无依据输出 Unity `Assets/` 或 Unreal `Content/` 结构。
- 需要外部编辑器操作时，优先使用受控 `engine_*` 能力；脚本文件写入可优先走工作区文件工具，MCP 只做其稳定支持的编辑器操作。
