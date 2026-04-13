# Ludens-Flow 项目状态

> 最后更新：2026-04-13

---

## 当前状态

项目已完成多 Agent 工作流主链路，具备基础前端、图片输入、可选联网搜索、多项目工作台与项目级 Unity 只读接入能力。当前阶段重点仍是“稳定优化 + 工程化整理 + 体验打磨”。

---

## 已完成

| 模块 | 当前状态 |
|---|---|
| 多 Agent 状态机工作流 | 已完成 Design -> PM -> Engineering -> Review 主链路与回流机制 |
| 状态持久化 | 已升级为 `StateStore`（文件锁 + 原子写 + revision 冲突检测），并完成 `state/` 模块化拆分 |
| Artifact 管理 | 已支持 GDD、PROJECT_PLAN、IMPLEMENTATION_PLAN、REVIEW_REPORT、DEVLOG 的读写与落盘 |
| Web API | 已提供 `/api/state`、`/api/chat`、`/api/projects`、`/api/projects/current/reset`、Unity 绑定接口及工作区文件读取接口 |
| 前端工作台 | 已具备多项目侧栏、工件查看、Agent 栏、中心对话区、只读历史查看、图片上传、即时消息回显与项目级重置 |
| 多模态输入 | 已支持文本 + 图片输入，前端可上传图片并转换为多模态消息 |
| 联网搜索 | 已接入 `ddgs` 搜索工具；未安装依赖时会降级为不可用而不阻塞主流程 |
| Unity 工程接入（只读） | 已支持项目级 `unity_root` 绑定/解绑，并接入列目录、读文件、按模式查找的公共只读工具（4 个 Agent 共用） |
| Workspace 规范化 | 已统一为根级 `workspace/` 工作台；项目运行数据落在 `workspace/projects/<project_id>/`，并支持旧单项目数据迁移 |
| 版本控制清理 | `workspace/` 已整体忽略，仅保留说明文档，避免日志和运行时状态入库 |
| 测试 | 已包含状态机、router、artifact、多项目工作区、workspace reset、tools 等测试文件 |

---

## 当前已知情况

- 联网搜索依赖 `ddgs`，属于可选能力；未安装时搜索功能不可用，但系统其余能力可正常运行。
- 当前前端已可用于演示和基本交互，且已拆分为 `index.html / styles.css / api.js / app.js` 四层结构，但仍处于“配合性优化”阶段。
- Unity 接入当前为只读模式（绑定路径 + 文件读取/检索），尚未开放工程文件写回与编辑器侧操作。
- `workspace/` 为运行时数据区，不应作为版本化资产管理；当前默认使用多项目目录结构。

---

## 下一步重点

当前后续开发计划已同步到 [ROADMAP.md](e:/GitDesktop/Ludens-Flow/11_docs/ROADMAP.md)，近期优先级如下：

1. 稳定优化，包括多模态扩展后的输入流、状态流和异常处理优化。
2. 安装包与工程化收口（`ludensflow` 包名、标准入口、`pyproject.toml` 完整化）。
3. Prompt 优化与结构化输出（Schemas），提高输出稳定性和可消费性。
4. 多项目工作台后续完善，包括项目元数据、归档语义与更多项目管理操作。
5. 前端配合性优化，继续改善工作台交互、状态展示与只读/编辑边界。
6. Unity 只读能力继续增强（`.meta`/引用关系解析）并评估后续受控写入路径。

---

## 关键目录

```text
Ludens-Flow/
├── agent_workbench/        # 多 Agent 引擎、API、前端与测试
├── 11_docs/                # 项目文档与规划
├── workspace/              # 运行时工作区根目录（项目数据位于 projects/ 下）
├── 00_meta/                # 规则与元数据
├── requirements.txt        # Python 依赖
└── STATUS.md               # 当前项目状态摘要
```

---

## 相关文档

- [Agent Workbench 使用说明](e:/GitDesktop/Ludens-Flow/agent_workbench/README.md)
- [Roadmap](e:/GitDesktop/Ludens-Flow/11_docs/ROADMAP.md)
- [Workspace 说明](e:/GitDesktop/Ludens-Flow/workspace/README.md)
