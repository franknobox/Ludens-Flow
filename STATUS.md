# Ludens-Flow 项目状态
> 最后更新：2026-06-05

---

## 当前状态

项目主链路稳定，仍处于 **v3 preview** 迭代阶段。近期完成了后端 API 入口拆分、游戏 AI 配置中心第一版、AIGC 入口更新、Unreal MCP 接入准备与插件排错、Level Layout Studio / 关卡设计台本地离线接入，以及 README / Roadmap 同步更新。

当前产品定位进一步明确为 **human-in-the-loop 的多 Agent 游戏开发工作台**：Agent 可以理解项目上下文、调用工具并推进任务，但关键配置、导出、执行和结果回流都需要保持用户可见、可确认、可修改、可覆盖。

---

## 已完成

| 模块 | 当前状态 |
|---|---|
| 多 Agent 主流程 | 已完成 `Design -> PM -> Engineering -> Review -> Decision / DEV_COACHING` 主链路与回流机制。 |
| 工程化入口 | 已完成 `pyproject.toml`、Web 启动脚本与 `ludensflow-api` 调试入口；`ludensflow` CLI 作为旧版 / 调试入口保留。 |
| 状态存储 | 已完成 `StateStore` 模块化拆分、revision 冲突检测、原子写入、锁文件与审计日志。 |
| 项目生命周期 | 已完成 `schema_version`、项目元数据迁移、项目导入 / 导出、旧 workspace 迁移；元数据写入已改为原子写，坏 meta 隔离，删除项目不会被 stale touch 复活。 |
| Artifact 管理 | 已支持 `GDD / PROJECT_PLAN / IMPLEMENTATION_PLAN / REVIEW_REPORT / DEVLOG` 的读写与冻结保护；前端支持人工编辑、Markdown 渲染与 DEVLOG pipeline。 |
| Prompt / Schemas | 已完成 discuss 共享 schema、ReviewGate schema、统一结构化解析、Prompt 分层模板与第一轮 prompt 重写。 |
| 用户画像 | 已完成项目级 `USER_PROFILE.md`、结构化模板、提示词注入规则增强、旧版画像迁移，并在设置页提供读取、编辑、保存入口。 |
| 上下文策略 | 已实现工作区文件树目录摘要自动生成，并在 EngineeringAgent 的 plan_discuss 和 coach 阶段注入上下文，使 Agent 进入对话时可感知工作区代码文件结构。 |
| Web API | API 入口已从单文件拆为 `app/api/` package，覆盖 chat、projects、workspaces、settings、copywriting、events 等分组；`api/common.py` 仍保留部分共享模型、事件与业务辅助函数，后续继续下沉并补 endpoint smoke 测试。 |
| 前端工作台 | 已具备项目侧栏、工件查看 / 编辑、Agent 对话、SSE 增量消息、工具进度事件、多格式附件、项目级操作、Markdown 阅读、暗色主题、AIGC 快捷入口、GitHub 可视化入口、MCP 工作台、游戏 AI 配置中心、文案加工台、Level Layout Studio / 关卡设计台等页面入口。 |
| 多项目工作台 | 已统一为 `workspace/projects/<project_id>/` 结构，并支持 active project / migrate / project meta。 |
| 游戏工程接入基础 | 已支持项目级工作区清单、目录读取、文本文件读写、路径逃逸拦截、可写开关与统一错误结构。 |
| MCP 引擎接入 | Blender MCP 实机验证通过；Unity MCP 已完成实机验证并修正为 stdio 交互配置；Unreal MCP 正在连接与验证，已处理插件安装路径、Python 依赖、UE5.7 编译兼容等问题，底层工具映射仍在补齐；Godot 保留最小参数校验与 workspace 路径沙箱。 |
| 多模型路由 | 已支持 `.env` 全局保底 + 项目级 `model_routing` 优先级路由；前端已提供图形化行式表单与 provider profile 下拉选择。 |
| 游戏 AI 配置中心 | 已完成场景配置、模型广场、自定义模型、测试调用、导出入口、行为树 / 任务线 / 多模态 / 图片 / 视频 / 声音等分类页面第一版；边界已明确为输出配置 JSON、示例代码与接入说明，不直接提供第三方模型 API。 |
| AIGC 能力入口 | 已保留并更新外部 AIGC 快捷入口目录，覆盖图片、声音、视频、模型、原型等方向；后续不再作为独立 roadmap 大项，而是并入 Agent 驱动的模块自动化与结果回流闭环。 |
| Level Layout Studio / 关卡设计台 | 已本地离线接入来源于 `kluiyao.itch.io` 的 layout tools，提供工作台同级入口、黑白风格图标、标题栏适配、导入导出保留、刷新不丢的本地保存、工具组 hover 菜单修复，并移除原工具内置 AI 面板。 |
| 文案能力基础 | 已提供 `DesignCopywritingRequest/Response` schema、normalize、job/SSE 生成链路、前端文案加工台、外部参考文件、过程状态展示、Markdown 导出与 Dialogue CSV 导出。 |
| Skills 外部导入 | 已支持 `workspace/skills/installed/<skill_id>/` 全局存储、外部 `skill.json` / `prompt.md` 导入、清单展示、删除、项目级启用开关与设置页管理。 |
| 前端稳定性 | HTTP reply 回填避免 SSE 断连白屏；Error Boundary 防白屏；SSE 订阅抖动修复；toolEvents 上限与 permission 清理；transient timeout 防泄漏；重复提交守卫。 |
| 测试 | 已完成测试收口与合并；近期涉及项目生命周期、Skills、用户画像与 MCP / 工具能力的回归测试通过。 |

---

## 当前已知情况

- Web 前端 SSE 实时同步链路已落地，HTTP reply 作为 SSE 降级兜底；设置页与工作台非默认功能页已拆为懒加载 chunk，但主包仍略高于 Vite 默认 500KB warning 阈值，后续可继续拆分 Markdown / highlight 等依赖。
- Prompt / Schema 基础能力已落地，但 `reply` 仍主要是字符串层协议，尚未升级为更细粒度的角色化结构。
- 工程文件工具当前已具备基础读写、目录创建、patch 与删除能力，但批量变更确认、编辑器侧操作与过程可视化仍需继续打磨。
- 游戏 AI 配置中心已有可浏览、可配置、可导出的第一版界面，但真实游戏运行时闭环尚未完成；后续重点是边界说明、零基础使用指南、模型广场快捷配置、自定义模型路由、流式输出、工具调用审计、缓存、频率限制、成本预算与降级策略。
- Unreal MCP 处于接入验证阶段，插件编译兼容、Python 依赖和工具映射正在逐步补齐；保存关卡、读取 Output Log、PIE 等底层工具仍需与工作台映射稳定。
- Level Layout Studio 当前已实现本地离线可用和浏览器刷新不丢，但保存仍主要依赖浏览器本地存储，尚未回流为项目 artifact；工作台 Agent 辅助关卡设计也还未接入。
- 外部 AIGC 目前以入口目录、跳转和快捷配置为主，结果回收、资产组织、账户权限和可替换调用还未形成完整闭环。
- Skills 当前具备外部导入和项目启用管理，但尚未进入 Agent 运行时自动加载与内部沉淀闭环。

---

## 下一步重点

当前后续开发计划已同步到 [ROADMAP](e:/GitDesktop/Ludens-Flow/11_docs/ROADMAP.md)，近期优先级如下：

1. 继续完成 Unreal MCP 连接与验证：补齐保存关卡、读取 Output Log、运行 / PIE、项目操作等底层工具映射，并保证 UE5.7 插件编译和 Python 服务链路稳定。
2. 推进游戏 AI 配置中心落地：明确模块边界，升级导出说明为使用指南，优化模型广场快捷配置、自定义模型与模型路由结合，并补齐调用策略、审计、缓存、频率限制、成本预算和降级策略。
3. 建设 Agent 驱动的模块自动化：让用户通过对话触发文案生成、AIGC 入口、MCP 操作、游戏 AI 配置、关卡设计等能力，同时保留手动流程、权限确认、审计记录和结果回流。
4. 完善 Level Layout Studio / 关卡设计台：将本地离线工具进一步接入项目 artifact、导入导出流程和 Agent 辅助设计能力，并保留来源标注。
5. 持续打磨前端工作台：优化页面浏览体验、暗浅色适配、抽屉 / 下拉控件、入口图标、项目状态一致性与刷新后的持久化体验。
6. 补齐 endpoint smoke 测试与核心工作流回归测试，覆盖 API 拆分后的路由、游戏 AI 配置导出、AIGC 目录、关卡设计台保存和 MCP 事件链路。

---

## 关键目录

```text
Ludens-Flow/
├── agent_workbench/        # 多 Agent 引擎、API、前端与测试
├── 11_docs/                # 项目文档与规划
├── workspace/              # 运行时工作区根目录，项目数据位于 projects/ 下
├── 00_meta/                # 规则、schemas 与元数据
├── requirements.txt        # Python 依赖
└── STATUS.md               # 当前项目状态摘要
```

---

## 相关文档

- [Agent Workbench 使用说明](e:/GitDesktop/Ludens-Flow/agent_workbench/README.md)
- [Roadmap](e:/GitDesktop/Ludens-Flow/11_docs/ROADMAP.md)
- [Workspace 说明](e:/GitDesktop/Ludens-Flow/workspace/README.md)
