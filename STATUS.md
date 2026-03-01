# Ludens-Flow — 项目状态

> 最后更新：2026-02-27

---

## 🏁 当前阶段

**多 Agent 架构 MVP 实现完成 · 基于状态机的工作流引擎已就绪**

---

## ✅ 已完成

| 模块 | 描述 |
|---|---|
| `agent_workbench/src/ludens_flow/state.py` | 实现了 `LudensState` 全局状态中心，支持进程级别的持久化断点续传 |
| `agent_workbench/src/ludens_flow/router.py` | 实现了基于 Phase 的核心路由大脑，负责状态流转、打回重做等逻辑 |
| `agent_workbench/src/ludens_flow/graph.py` | 实现了 Graph 图节点调度器，对接路由与各执行实体 |
| `agent_workbench/src/ludens_flow/artifacts.py` | 实现了核心产物（GDD、实现计划等）的单写入权与原子化版本落盘 |
| `agent_workbench/src/ludens_flow/agents/` | 封装了四大核心节点：Design / PM / Engineering / Review |
| **状态流转基线** | 完整跑通 Design → PM → Engineering → Review 并在必要时 Backflow 回退的环形图流转 |
| **独立 Unity 游戏开发特化 (新)** | 将四大子 Agent 提示词重构：默认基于 Unity 引擎进行独立开发/Game Jam，剔除商业化及联机内容，产出实用的底层目录架构。 |
| **CI 与端到端测试覆盖 (新)** | 修复并重构全部 7 个核心图流转测试，补齐跨 Agent 状态流转断言。通过新增带超时保护的全链路真实 LLM 测试，确保 Prompt 与状态机可靠性。 |
| **代码精简与隔离** | 移除了无关的早期里程碑测试文件与废弃的 `orchestrator.py` 以及过时的调度代码。实现了严格的测试环境状态目录隔离。 |

---

## 🔄 进行中 / 开发计划 (Roadmap)

我们已将后续核心规划梳理至独立文档：[ROADMAP.md](docs/ROADMAP.md)

以下为核心摘要重点：
- [ ] **Prompt 与 Schema 优化**：引入强结构化输出 (JSON Schemas) 保障流转稳定性。
- [ ] **人设独立与可配**：将各 Agent 的 System Prompt 与用户画像 (User Profile) 抽离为独立配置文件，实现动态自适应对话。
- [ ] **多模态与联网搜索**：集成 Web Search API 与图像识别 (如 GPT-4V)，解决时效性问题并允许处理截图/引擎报错。
- [ ] **前端交互 UI**：设计并开发图形化前端（如 Gradio / Streamlit 等），将 CLI 交互升级为可视化的工作台与文件对比视图。

---

## 📁 目录结构（核心资产）

```
Ludens-Flow/
├── agent_workbench/        # Agent 执行引擎
│   ├── src/ludens_flow/    # 核心框架流转与逻辑代码 (State/Router/Graph/Artifacts)
│   │   └── agents/         # 具体 Agent 实现 (Design/PM/Engineering/Review)
│   ├── llm/                # LLM 调用层
│   └── tests/              # 测试脚本与错误 dump
├── docs/                   # 项目文档与规划
│   └── ROADMAP.md          # 后续开发计划
├── workspace/              # 运行时生成空间（执行产生，自动生成）
│   ├── logs/               # trace.log/router.log 等运行日志
│   ├── memory/             # 历史对话与 Agent 记忆
│   └── state.json          # 全局流转状态存档
├── Unity/                  # Unity 游戏工程
├── .env                    # LLM配置（不入库）
└── STATUS.md               # 本文件
```

---

## ⚙️ 环境信息

| 项目 | 值 |
|---|---|
| LLM Provider | `openai`（Moonshot AI 兼容接口） |
| Model | `kimi-k2-turbo-preview` |
| Base URL | `https://api.moonshot.cn/v1` |
| Python | 3.x |

---

## 🔗 相关文档

- [Agent Workbench 使用指南](agent_workbench/README.md)
- [后续详细开发计划 (ROADMAP)](docs/ROADMAP.md)
