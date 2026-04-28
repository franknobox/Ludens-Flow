# Ludens-Flow 项目状态
> 最后更新：2026-04-26

---

## 当前状态
项目主链路已经稳定运行，具备多 Agent 工作流、项目级状态管理、多项目工作台、Web/API/CLI 三套入口，以及项目工作区受控读写能力。近期重点集中在前端产品化扩展、工程工具能力补齐、Markdown 工件阅读体验与收版验收基线固化。

---

## 已完成
| 模块 | 当前状态 |
|---|---|
| 多 Agent 主流程 | 已完成 `Design -> PM -> Engineering -> Review -> Decision / DEV_COACHING` 主链路与回流机制 |
| 工程化入口 | 已完成 `pyproject.toml`、标准入口命令 `ludensflow / ludensflow-api` 与安装启动 smoke test |
| 状态存储 | 已完成 `StateStore` 模块化拆分、revision 冲突检测、原子写入、锁文件与审计日志 |
| 项目生命周期 | 已完成 `schema_version`、项目元数据迁移、项目导入/导出、旧 workspace 迁移 |
| Artifact 管理 | 已支持 `GDD / PROJECT_PLAN / IMPLEMENTATION_PLAN / REVIEW_REPORT / DEVLOG` 的读写与冻结保护；前端已支持人工编辑、Markdown 渲染与 DEVLOG pipeline（冻结仅限制 Agent 自动提交） |
| Prompt / Schemas | 已完成 discuss 共享 schema、ReviewGate schema、统一结构化解析、Prompt 分层模板与第一轮 prompt 重写 |
| 用户画像 | 已完成项目级 `USER_PROFILE.md`、结构化模板、提示词注入规则增强与旧版画像迁移 |
| Web API | 已提供 `/api/state`、`/api/chat`、`/api/projects`、项目级 reset、SSE 事件推送、工作区文件读取/写入、目录创建、文件删除与项目 settings 更新接口 |
| 前端工作台 | 已具备项目侧栏、工件查看/编辑、Agent 对话、SSE 增量消息、工具进度事件、多格式附件、项目级操作、Markdown 阅读、暗色主题、AIGC 快捷入口、GitHub 可视化入口、Game Model 与 MCP 页面入口；设置页支持工具、工作区与通用写入配置查看 |
| 多项目工作台 | 已统一为 `workspace/projects/<project_id>/` 结构，并支持 active project / migrate / project meta |
| 游戏工程接入（基础） | 已支持项目级工作区清单、目录读取、文本文件读取/写入、路径逃逸拦截、可写开关与统一错误结构 |
| 多模型路由 | 已支持 `.env` 全局保底 + 项目级 `model_routing`（global/agents/capabilities/agent_capabilities）优先级路由 |
| 测试 | 已完成测试收口与合并；当前后端全量结果为 `107 passed` |

---

## 当前已知情况
- Web 前端 SSE 实时同步链路已落地，但首屏与少量兜底场景仍保留全量刷新路径。
- Prompt / Schema 基础能力已落地，但 `reply` 仍主要是字符串层协议，尚未升级为更细粒度的角色化结构。
- 工程文件工具当前已具备基础读写、目录创建、patch 与删除能力，但批量变更确认、编辑器侧操作与过程可视化仍需继续打磨。
- AIGC、GitHub、Game Model、MCP 等新页面目前以“前端入口 / 页面壳 / 快捷目录”为主，真实后端集成仍需分阶段接入。
- 多模型路由当前以 JSON 配置为主，尚未提供更细粒度的图形化路由编辑器（如 provider/model 下拉与校验向导）。
- 收版验收基线（benchmark、核心指标看板、Release Checklist）尚未固化为流程闸门。

---

## 下一步重点
当前后续开发计划已同步到 [ROADMAP](e:/GitDesktop/Ludens-Flow/11_docs/ROADMAP.md)，近期优先级如下：
1. 继续完善受控工具能力：路径审核、写入确认、patch/delete/create-dir 等工程文件操作与过程事件展示。
2. 推进游戏工程接入：Unity 编辑器 MCP / 工具层方案验证，并预留 Godot、UE 等更多引擎兼容方向。
3. 持续打磨前端工作台：页面壳、导航、设置页、工具目录、AIGC 快捷入口、GitHub / Game Model / MCP 页面与项目状态一致性。
4. 固化收版验收基线：benchmark、核心指标看板与 Release Checklist。

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
