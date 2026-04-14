# Ludens-Flow 项目状态
> 最后更新：2026-04-14

---

## 当前状态
项目主链路已经稳定运行，具备多 Agent 工作流、项目级状态管理、多项目工作台、Web/API/CLI 三套入口，以及 Unity 工程只读接入的基础能力。当前阶段重点是“V3 收版前的稳定性门禁 + Prompt/Schema 深化 + 前端实时体验打磨”。

---

## 已完成
| 模块 | 当前状态 |
|---|---|
| 多 Agent 主流程 | 已完成 `Design -> PM -> Engineering -> Review -> Decision / DEV_COACHING` 主链路与回流机制 |
| 工程化入口 | 已完成 `pyproject.toml`、标准入口命令 `ludensflow / ludensflow-api` 与安装启动 smoke test |
| 状态存储 | 已完成 `StateStore` 模块化拆分、revision 冲突检测、原子写入、锁文件与审计日志 |
| 项目生命周期 | 已完成 `schema_version`、项目元数据迁移、项目导入/导出、旧 workspace 迁移 |
| Artifact 管理 | 已支持 `GDD / PROJECT_PLAN / IMPLEMENTATION_PLAN / REVIEW_REPORT / DEVLOG` 的读写与冻结保护 |
| Prompt / Schemas | 已完成 discuss 共享 schema、ReviewGate schema、统一结构化解析、Prompt 分层模板与第一轮 prompt 重写 |
| 用户画像 | 已完成项目级 `USER_PROFILE.md`、结构化模板、提示词注入规则增强与旧版画像迁移 |
| Web API | 已提供 `/api/state`、`/api/chat`、`/api/projects`、项目级 reset、Unity 绑定与工作区文件读取接口 |
| 前端工作台 | 已具备项目侧栏、工件查看、Agent 对话、即时消息回显、思考态、图片上传与项目级 reset |
| 多项目工作台 | 已统一为 `workspace/projects/<project_id>/` 结构，并支持 active project / migrate / project meta |
| Unity 工程接入（基础） | 已支持项目级 `unity_root` 绑定、目录读取、文本文件读取与路径逃逸拦截 |
| 测试 | 已完成测试收口与合并；当前保留 9 个测试文件，全量结果为 `66 passed, 1 skipped` |

---

## 当前已知情况
- Web 前端已经可用，但实时同步仍以请求驱动为主，SSE / 增量刷新尚未完成。
- Prompt / Schema 基础能力已落地，但 `reply` 仍主要是字符串层协议，尚未升级为更细粒度的角色化结构。
- Unity 接入当前仍以只读为主，尚未开放工程文件写回与编辑器侧操作。
- 主链路里的开发期 `print` 调试输出已清理，测试也已合并收口，但日志分级和输出噪音仍有进一步打磨空间。

---

## 下一步重点
当前后续开发计划已同步到 [ROADMAP](e:/GitDesktop/Ludens-Flow/11_docs/ROADMAP.md)，近期优先级如下：
1. 推进 V3 收版必做项 4/5/6：前端实时同步、Unity 只读安全边界、收版验收基线。
2. 继续深化 Prompt / Schema：做真实场景对打、优化角色化 `reply` 协议，并收敛前端消费方式。
3. 持续打磨前端工作台的状态一致性、阶段反馈与文件输入体验。
4. 继续增强 Unity 工程文件辅助能力，为后续更深的工程协作打底。

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
