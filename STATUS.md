# Ludens-Flow 项目状态

> 最后更新：2026-03-16

---

## 当前状态

项目已完成多 Agent 工作流的可运行主链路，并具备基础前端、图片输入和可选联网搜索能力。当前阶段的重点已从“能跑通”转向“稳定优化与体验打磨”。

---

## 已完成

| 模块 | 当前状态 |
|---|---|
| 多 Agent 状态机工作流 | 已完成 Design -> PM -> Engineering -> Review 主链路与回流机制 |
| 状态持久化 | 已具备 `LudensState` 持久化、阶段切换、对话历史和 transcript 历史记录 |
| Artifact 管理 | 已支持 GDD、PROJECT_PLAN、IMPLEMENTATION_PLAN、REVIEW_REPORT、DEVLOG 的读写与落盘 |
| Web API | 已提供 `/api/state`、`/api/chat`、`/api/reset` 以及工作区文件读取接口 |
| 前端工作台 | 已具备文件栏、Agent 栏、中心对话区、只读历史查看、图片上传与会话重置 |
| 多模态输入 | 已支持文本 + 图片输入，前端可上传图片并转换为多模态消息 |
| 联网搜索 | 已接入 `ddgs` 搜索工具；未安装依赖时会降级为不可用而不阻塞主流程 |
| Workspace 规范化 | 已统一为根级 `workspace/`，运行时目录自动生成，旧路径已迁移清理 |
| 版本控制清理 | `workspace/` 已整体忽略，仅保留说明文档，避免日志和运行时状态入库 |
| 测试 | 已包含状态机、router、artifact、freeze、workspace reset、tools 等测试文件 |

---

## 当前已知情况

- 联网搜索依赖 `ddgs`，属于可选能力；未安装时搜索功能不可用，但系统其余能力可正常运行。
- 当前前端已可用于演示和基本交互，但仍处于“配合性优化”阶段，不是最终形态。
- `workspace/` 为运行时数据区，不应作为版本化资产管理。

---

## 下一步重点

当前后续开发计划已同步到 [ROADMAP.md](e:/GitDesktop/Ludens-Flow/docs/ROADMAP.md)，近期优先级如下：

1. 稳定优化，包括多模态扩展后的输入流、状态流和异常处理优化。
2. 独立系统人设与用户人设文件，降低 prompt 和角色配置耦合。
3. Prompt 优化与结构化输出（Schemas），提高输出稳定性和可消费性。
4. 多项目工作台化，支持多项目隔离的运行空间与上下文切换。
5. 前端的配合性优化，继续改善工作台交互、状态展示和只读/编辑边界。

---

## 关键目录

```text
Ludens-Flow/
├── agent_workbench/        # 多 Agent 引擎、API、前端与测试
├── docs/                   # 项目文档与规划
├── workspace/              # 运行时工作区（自动生成，默认不入库）
├── Unity/                  # Unity 项目目录
├── requirements.txt        # Python 依赖
└── STATUS.md               # 当前项目状态摘要
```

---

## 相关文档

- [Agent Workbench 使用说明](e:/GitDesktop/Ludens-Flow/agent_workbench/README.md)
- [Roadmap](e:/GitDesktop/Ludens-Flow/docs/ROADMAP.md)
- [Workspace 说明](e:/GitDesktop/Ludens-Flow/workspace/README.md)
