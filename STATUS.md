# Ludens-Flow 项目状态
> 最后更新：2026-05-05

---

## 当前状态
项目主链路稳定，已进入 **v3 preview** 阶段。近期集中完成了 MCP 稳定性加固、工作区文件树上下文自动注入、聊天自动滚底体验优化、项目元数据持久化保护等。核心能力覆盖多 Agent 工作流、项目级状态管理、工作区受控读写、Blender/Unity MCP 实机调用与工具事件可观测性。

---

## 已完成

| 模块 | 当前状态 |
|---|---|
| 多 Agent 主流程 | 已完成 `Design -> PM -> Engineering -> Review -> Decision / DEV_COACHING` 主链路与回流机制 |
| 工程化入口 | 已完成 `pyproject.toml`、Web 启动脚本与 `ludensflow-api` 调试入口；`ludensflow` CLI 作为旧版/调试入口保留 |
| 状态存储 | 已完成 `StateStore` 模块化拆分、revision 冲突检测、原子写入、锁文件与审计日志 |
| 项目生命周期 | 已完成 `schema_version`、项目元数据迁移、项目导入/导出、旧 workspace 迁移；元数据写入已改为原子写（temp + os.replace），坏 meta 隔离，删除项不会被 stale touch 复活 |
| Artifact 管理 | 已支持 `GDD / PROJECT_PLAN / IMPLEMENTATION_PLAN / REVIEW_REPORT / DEVLOG` 的读写与冻结保护；前端已支持人工编辑、Markdown 渲染与 DEVLOG pipeline（冻结仅限制 Agent 自动提交） |
| Prompt / Schemas | 已完成 discuss 共享 schema、ReviewGate schema、统一结构化解析、Prompt 分层模板与第一轮 prompt 重写 |
| 用户画像 | 已完成项目级 `USER_PROFILE.md`、结构化模板、提示词注入规则增强、旧版画像迁移，并在设置页提供读取、编辑、保存入口 |
| 上下文策略 | 已实现工作区文件树目录摘要自动生成，并在 EngineeringAgent 的 plan_discuss 和 coach 阶段进行上下文注入，使 Agent 进入对话时即可感知工作区代码文件结构 |
| Web API | 已提供 `/api/state`、`/api/chat`、`/api/projects`、项目级 reset、SSE 事件推送、工作区文件读取/写入、目录创建、文件删除与项目 settings 更新接口；API 入口已拆为 `app/api/` 分组模块 |
| 前端工作台 | 已具备项目侧栏、工件查看/编辑、Agent 对话、SSE 增量消息、工具进度事件、多格式附件、项目级操作、Markdown 阅读、暗色主题、AIGC 快捷入口（含文字创作分组）、GitHub 可视化入口、Game Model / MCP / Skills / 文案加工台页面入口；设置页支持通用设置、用户画像、Skills 管理、模型路由图形化编辑、工具、工作区、引擎连接与历史项目；已对设置页与工作台非默认功能页做页面级懒加载；聊天面板已支持随消息或流式输出自动滚底 |
| 多项目工作台 | 已统一为 `workspace/projects/<project_id>/` 结构，并支持 active project / migrate / project meta |
| 游戏工程接入（基础） | 已支持项目级工作区清单、目录读取、文本文件读取/写入、路径逃逸拦截、可写开关与统一错误结构 |
| MCP 引擎接入 | Blender MCP 实机验证通过（`engine_list_scene`、`engine_create_object`、`engine_save_scene`）；Unity MCP 已完成实机验证并修正为 stdio 交互配置；Godot/Unreal 已补最小参数校验与 workspace 路径沙箱；health 模块已重构支持跨传输层与时序状态处理；工具事件边界已收敛 |
| 多模型路由 | 已支持 `.env` 全局保底 + 项目级 `model_routing`（global/agents/capabilities/agent_capabilities）优先级路由；前端已提供图形化行式表单与 provider profile 下拉选择 |
| 文案能力（基础） | 已提供 `DesignCopywritingRequest/Response` schema、normalize、job/SSE 生成链路、前端文案加工台、外部参考文件、过程状态展示、Markdown 导出与 Dialogue CSV 导出 |
| Skills 外部导入 | 已支持 `workspace/skills/installed/<skill_id>/` 全局存储、外部 `skill.json` / `prompt.md` 导入、清单展示、删除、项目级启用开关与设置页管理 |
| 前端稳定性 | HTTP reply 回填避免 SSE 断连盲屏；Error Boundary 防白屏；SSE 订阅抖动修复；toolEvents 上限与 permission 清理；transient timeout 防泄漏；重复提交守卫 |
| 测试 | 已完成测试收口与合并；近期涉及项目生命周期、Skills、用户画像与 MCP/工具能力的回归测试通过 |

---

## 当前已知情况
- Web 前端 SSE 实时同步链路已落地，HTTP reply 作为 SSE 降级兜底；设置页与工作台非默认功能页已拆为懒加载 chunk，但主包仍略高于 Vite 默认 500KB warning 阈值，后续可继续拆分 Markdown/highlight 等依赖。
- `theme-dark.css` 已批量清理 `!important`，暗色主题特异性改为靠 `[data-theme="dark"]` 前缀，未来主题切换与动态样式更容易覆盖。
- Prompt / Schema 基础能力已落地，但 `reply` 仍主要是字符串层协议，尚未升级为更细粒度的角色化结构。
- 工程文件工具当前已具备基础读写、目录创建、patch 与删除能力，但批量变更确认、编辑器侧操作与过程可视化仍需继续打磨。
- AIGC、GitHub、Game Model 等新页面目前以"前端入口 / 页面壳 / 快捷目录"为主，部分能力已接入真实读取或状态接口，完整后端集成仍需分阶段推进。
- Skills 当前已具备外部导入和项目启用管理，但尚未进入 Agent 运行时自动加载与内部自沉淀闭环。

---

## 下一步重点
当前后续开发计划已同步到 [ROADMAP](e:/GitDesktop/Ludens-Flow/11_docs/ROADMAP.md)，近期优先级如下：
1. 继续打磨 MCP 实机体验：Blender 材质/颜色属性传递、viewport 截图、更细粒度的工具映射与错误提示。
2. 完善受控工具能力：路径审核、写入确认、patch/delete/create-dir 等工程文件操作与过程事件展示。
3. 推进游戏工程接入：Unity 编辑器 MCP / 工具层方案验证，并预留 Godot、UE 等更多引擎兼容方向。
4. 持续打磨前端工作台：页面壳、导航、设置页、工具目录、AIGC 快捷入口、GitHub / Game Model / MCP / Skills 页面与项目状态一致性。

---

## 关键目录

```text
Ludens-Flow/
├─ agent_workbench/        # 多 Agent 引擎、API、前端与测试
├─ 11_docs/                # 项目文档与规划
├─ workspace/              # 运行时工作区根目录（项目数据位于 projects/ 下）
├─ 00_meta/                # 规则、schemas 与元数据
├─ requirements.txt        # Python 依赖
└─ STATUS.md               # 当前项目状态摘要
```

---

## 相关文档
- [Agent Workbench 使用说明](e:/GitDesktop/Ludens-Flow/agent_workbench/README.md)
- [Roadmap](e:/GitDesktop/Ludens-Flow/11_docs/ROADMAP.md)
- [Workspace 说明](e:/GitDesktop/Ludens-Flow/workspace/README.md)
