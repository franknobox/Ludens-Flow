# Ludens-Flow 游戏开发辅助能力

## 1. 文档定位

本文档记录 Ludens-Flow 面向游戏开发的专项能力设计。  
它不覆盖通用 Agent 工作流，也不重复 Roadmap 中的全部规划，重点说明：

- 当前已经具备哪些游戏开发相关能力。
- 近期要补齐哪些工程、引擎和内容生产能力。
- Unity、Blender、Godot、UE 等方向如何放进同一套能力模型。
- 哪些能力必须统一经过工作区边界、权限确认和过程展示。

---

## 2. 当前能力现状

### 2.1 工作台与工件

当前已经具备：

- 多 Agent 工作流：Design / PM / Engineering / Review / Dev Coaching。
- 项目级工件：`GDD.md`、`PROJECT_PLAN.md`、`IMPLEMENTATION_PLAN.md`、`REVIEW_REPORT.md`、`DEVLOG.md`、`NOTES.md`。
- 多项目工作台与项目级状态隔离。
- 项目级 `USER_PROFILE.md` 与设置页编辑入口。
- 文案加工台页面壳与基础 API。

这些能力构成游戏开发辅助的上层组织结构：设计、计划、工程、评审和开发笔记有固定位置，不再只停留在聊天记录中。

### 2.2 文件与工作区能力

当前已经具备：

- 项目级工作区清单。
- 工作区路径审核与边界限制。
- 文本文件读取、批量读取。
- 创建目录。
- 写入文本文件。
- Patch 文件。
- 删除文件。
- 写入总开关。
- 每次写入确认 / 安全自动执行两种模式。
- 工具事件与前端过程展示基础。

这一层是后续 Unity / Godot / Blender / UE 能力的共同安全边界。  
任何游戏工程文件操作都不应绕过工作区清单和权限层。

### 2.3 MCP 与外部工具入口

当前已经具备：

- 设置页“引擎连接”配置入口。
- Unity / Blender / Godot / Unreal 的 MCP 连接配置与健康检查 UI。
- Unity MCP 控制台页面。
- Blender MCP 控制台页面。
- Godot / Unreal 仍保持 Coming Soon 占位。
- 统一工具白名单与能力映射的初步设计。

现阶段 MCP 重点是配置、检查和能力模型收口。  
真实 Agent 调用仍应先通过 Ludens-Flow 自己的能力层，而不是直接暴露原始 MCP tools。

### 2.4 多模态与附件

当前已经具备：

- 图片附件理解。
- PDF / Markdown / 文本 / 代码文件附件解析。
- 粘贴、选择文件、拖拽上传的统一附件入口。
- 对话记录中附件摘要展示。

这些能力可用于游戏参考图、设定文档、已有代码、证明材料和外部资料进入当前对话。

---

## 3. 统一能力模型

游戏开发辅助能力不要按“某个引擎一个系统”来做，而应收敛到统一能力层。

建议统一抽象为：

```text
project/workspace
├─ read context
├─ search files
├─ create directory
├─ write file
├─ patch file
├─ delete file
├─ run command
└─ call engine capability
```

引擎能力再映射为：

```text
engine.list_scene
engine.read_console
engine.create_script
engine.create_object
engine.move_object
engine.save_scene
engine.run_project
```

底层可以来自：

- Unity MCP
- Blender MCP
- Godot MCP / Editor Plugin
- Unreal MCP / Editor 工具桥
- 普通工作区文件工具

但 Agent 不应直接面对底层工具名。  
Agent 应使用 Ludens-Flow 的统一能力名，由系统负责权限、映射、执行和反馈。

---

## 4. Unity 方向

Unity 是当前最优先落地方向。

### 4.1 当前已具备

- 项目级工作区绑定。
- `.cs` 等文本文件的读取、写入、patch 和删除能力。
- Unity MCP 页面与连接状态展示。
- Unity 能力白名单雏形：
  - 读取场景结构
  - 读取 Console
  - 创建脚本
  - 创建对象
  - 移动对象
  - 保存场景
  - 运行项目

### 4.2 近期重点

- 做稳 Unity 工程阅读与检索：
  - 搜索脚本。
  - 批量读取相关文件。
  - 根据错误日志定位文件。
  - 收集本轮参考文件。
- 做稳 `.cs` 文件修改闭环：
  - 读相关文件。
  - 生成 patch。
  - 展示 diff。
  - 用户确认。
  - 写入。
  - 记录变更。
- 推进 Unity Editor MCP 受控接入：
  - 读取 Hierarchy / Scene。
  - 读取 Console。
  - 创建脚本。
  - 放置 Prefab / 创建 GameObject。
  - 移动物体。
  - 保存场景。

### 4.3 暂缓项

- 直接修改复杂 `.prefab` / `.unity` YAML。
- 无确认的编辑器写操作。
- 高风险批量资源改名、移动和删除。

这些能力必须等 diff、权限确认、回滚提示和审计记录更稳定后再推进。

---

## 5. Blender 方向

Blender 是近期新增的内容生产能力方向，定位是 3D 资产与场景辅助，而不是替代游戏引擎。

### 5.1 当前已具备

- Blender MCP 控制台页面。
- Blender 连接配置入口。
- Blender 能力名单与底层工具映射提示。

当前页面覆盖的统一能力包括：

- `engine.list_scene`
- `engine.create_object`
- `engine.move_object`
- `engine.save_scene`
- `engine.create_script`
- `engine.run_project`

### 5.2 近期重点

- 接入 Blender MCP 的工具发现结果。
- 将 Blender 原始工具映射到统一能力层。
- 优先支持只读能力：
  - 读取场景信息。
  - 读取对象列表。
  - 读取对象属性。
- 再逐步开放受控写操作：
  - 创建基础对象。
  - 修改 Transform。
  - 保存 `.blend`。
- 对 `execute_blender_code` / Blender Python 执行类能力设置高风险权限。

### 5.3 安全边界

Blender Python 能力非常强，不应直接作为普通工具暴露给 Agent。  
第一版建议：

- 默认关闭。
- 必须单次确认。
- 显示执行意图和脚本摘要。
- 禁止访问项目工作区以外路径。
- 执行结果必须进入工具事件流。

---

## 6. 文案与表达能力

文案能力归属于 Design Agent，是策划能力的子能力，不单独作为独立 Agent。

### 6.1 当前已具备

- 文案加工台页面。
- `DesignCopywritingRequest/Response` schema。
- 基础生成 API。
- 前端结果展示。
- 单条复制、Markdown 导出、CSV 批量导出能力。

### 6.2 近期重点

- 接入 Design Agent 的项目上下文：
  - GDD。
  - 设定文档。
  - NOTES。
  - 用户输入的用途和限制。
- 支持更稳定的文案类型：
  - 角色台词。
  - 物品描述。
  - 世界观片段。
  - 地名 / 角色名 / 物品名。
  - UI 文案。
  - 任务描述。
- 支持约束条件：
  - 数量。
  - 长度。
  - 写作风格。
  - 必须包含。
  - 必须避免。
  - 使用场景。

文案输出应继续保持结构化，方便复制、导出和后续写入工件。

---

## 7. Godot 方向

Godot 放在远期兼容规划中，但值得保留较高优先级。

原因：

- 引擎开源。
- 项目文件文本化程度高。
- `.gd`、`.tscn`、`.tres` 等文件适合阅读、diff 和 patch。
- Editor Plugin / MCP 工具桥的操作空间较大。

后续重点：

- 读取 `project.godot`。
- 读取和修改 `.gd`。
- 读取 `.tscn` 场景结构。
- 通过 Godot MCP / Editor Plugin 获取节点树和运行输出。
- 与统一工作区权限、diff 和工具事件层打通。

Godot 不应另起一套产品逻辑，而应复用 Unity 已经验证过的工程执行闭环。

---

## 8. Unreal 方向

UE 放在远期兼容规划中，优先级低于 Unity 和 Godot。

早期切入点应是工程理解，而不是深度资源编辑：

- `.uproject`
- `Config/*.ini`
- `Source/**/*.h`
- `Source/**/*.cpp`
- `*.Build.cs`
- `*.Target.cs`
- `Plugins/`

UE 的资源、蓝图和编辑器自动化能力复杂度高，建议后续分阶段评估：

1. 只读工程结构。
2. C++ 工程辅助。
3. 配置和构建问题定位。
4. 编辑器侧 MCP / 工具桥。
5. 蓝图和资源能力。

---

## 9. 前端展示要求

游戏开发辅助能力必须在前端可见，不能只停留在后端工具调用。

需要持续打磨：

- 当前项目和工作区状态。
- Agent 正在读取哪些文件。
- Agent 正在调用哪些工具。
- 工具调用是否需要权限。
- 文件 diff 和变更摘要。
- 命令或编辑器操作输出。
- MCP 连接状态和工具映射状态。
- 本轮参考文件和本轮修改文件。

这部分应与“工程执行闭环”共用同一套事件流，而不是每种工具单独实现 UI。

---

## 10. 近期开发顺序

建议按以下顺序推进：

1. **工程执行闭环基础**
   - 文件检索、读取、patch、diff 展示、确认、写入、工具事件展示。

2. **Unity `.cs` 真实项目闭环**
   - 选一个小 Unity 项目，跑通“定位脚本 -> 修改脚本 -> 展示 diff -> 写入 -> 读取结果”。

3. **Unity Editor MCP 只读能力**
   - 先接 Scene / Hierarchy / Console。

4. **Blender MCP 只读能力**
   - 先接场景信息和对象列表。

5. **文案加工台接入 Design Agent 上下文**
   - 让生成结果真正参考 GDD / NOTES / 用户约束。

6. **高风险工具权限细化**
   - 对删除、命令执行、Blender Python、编辑器写操作做更明确的权限等级。

---

## 11. 非目标

当前阶段不做：

- 把 Ludens-Flow 做成通用文件管理器。
- 直接暴露原始 MCP tools 给 Agent。
- 默认允许无确认的编辑器写操作。
- 一次性覆盖所有引擎的完整能力。
- 自动修改复杂二进制资源或高风险场景文件。
- 用文案能力替代完整剧情编辑器。

---

## 12. 成功标准

近期成功标准应具体、可验证：

- Agent 能在绑定工作区内稳定读取和修改真实工程文件。
- 用户能在前端看见工具过程、权限请求和文件变更。
- Review 后的开发辅导能接上前面 GDD / 计划 / 工程方案。
- Unity `.cs` 修改能跑通端到端闭环。
- Blender MCP 至少能稳定发现工具并读取基础场景信息。
- 文案加工台能基于项目工件和约束生成可复制、可导出的结果。

这些标准可以纳入后续 Benchmark，而不是只作为主观目标。
