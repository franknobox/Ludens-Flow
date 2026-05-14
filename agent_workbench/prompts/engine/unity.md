# Unity Prompt Fragment

- 默认按 Unity 小团队项目思路落地，优先考虑 Scene、Prefab、MonoBehaviour、ScriptableObject、Inspector 配置和 `Assets/` 目录组织。
- 工程建议应兼顾 Unity 生命周期、组件拆分、序列化字段、Prefab 引用、Tag/Layer、Physics/Physics2D、Input System 与场景保存。
- 文件建议以 `Assets/...` 为边界；脚本通常使用 C#，避免无依据推荐 Godot GDScript 或 Unreal Blueprint。
- 需要外部编辑器操作时，优先使用受控 `engine_*` 能力；写入文件仍必须遵守项目工作区和权限设置。
