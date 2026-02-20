# Ludens-Flow — 项目状态

> 最后更新：2026-02-20

---

## 🏁 当前阶段

**Baseline 验证完成 · 多Agent架构设计中**

---

## ✅ 已完成

| 模块 | 描述 |
|---|---|
| `agent_workbench/llm/` | LLM 统一调用层（openai / OpenAI-compatible） |
| `agent_workbench/run_baseline.py` | 串行基线流程：Design → PM → Engineering → Review |
| `artifacts/gdd/GDD.md` | 首次 GDD 产物生成验证通过 |
| `artifacts/pm/PROJECT_PLAN.md` | 项目计划产物生成验证通过 |
| `artifacts/coding/IMPLEMENTATION_PLAN.md` | 实现计划产物生成验证通过 |
| `artifacts/review/REVIEW_REPORT.md` | 评审报告产物生成验证通过 |
| 终端输入模式 | 支持命令行参数 / 交互式 `input()` 两种方式 |
| 终端进度反馈 | 每个 Agent 阶段打印 `[N/4]` 进度提示 |

**最后成功运行阶段：** `review`（全流程 PASS）

---

## 🔄 进行中

- [ ] 多Agent架构重构方案设计
  - 目标：`OrchestratorAgent` (1) + 专职子Agent (4) 的真正多Agent结构
  - 核心增加：`SharedContext` 共享状态 · 迭代反馈循环 · Review PASS/FAIL 自动决策

---

## 📋 待办事项

| 优先级 | 任务 |
|---|---|
| 🔴 高 | 抽取 `core/context.py`（SharedContext）|
| 🔴 高 | 抽取 `agents/base.py`（BaseAgent 抽象类）|
| 🔴 高 | 4个 `generate()` 迁移为独立 Agent 类 |
| 🟡 中 | 实现 `OrchestratorAgent` + 迭代主控循环 |
| 🟡 中 | Review Agent 解析 PASS/FAIL，注入阻塞问题 |
| 🟢 低 | PM Agent + Engineering Agent 并行执行 |
| 🟢 低 | 结构化输出（Pydantic 替代纯 Markdown 解析）|

---

## 📁 目录结构（当前）

```
Ludens-Flow/
├── agent_workbench/        # Agent 执行引擎
│   ├── llm/                # LLM 调用层
│   ├── run_baseline.py     # 当前入口（串行基线）
│   └── README.md
├── artifacts/              # Agent 产出工件
│   ├── gdd/GDD.md
│   ├── pm/PROJECT_PLAN.md
│   ├── coding/IMPLEMENTATION_PLAN.md
│   └── review/REVIEW_REPORT.md
├── 00_meta/                # 规范与Schema
├── docs/                   # 项目文档
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
- [多Agent重构计划](agent_workbench/README.md) *(规划中)*
