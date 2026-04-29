# Ludens-Flow

<p align="center">
  <img src="11_docs/IMAGE/LF.svg" alt="Ludens-Flow logo" width="96" />
</p>

<p align="center">
  <strong>An agent-native workbench for structured game development.</strong>
</p>

<p align="center">
  <a href="#english">English</a> ·
  <a href="#简体中文">简体中文</a>
</p>

<p align="center">
  <a href="https://github.com/franknobox/Ludens-Flow">GitHub</a> ·
  <a href="agent_workbench/README.md">Workbench Docs</a> ·
  <a href="LICENSE">MIT License</a>
</p>

---

## English

### What Is Ludens-Flow?

Ludens-Flow is a multi-agent game development workbench built around explicit artifacts, controlled tools, and project-level state.

It is designed to help teams and solo developers structure game development work, not just chat with a model.

Instead of treating the agent as a free-form assistant, Ludens-Flow puts it back inside an engineering system:

- services have boundaries
- outputs have schemas
- tools have permissions
- tasks have state
- projects have workspaces
- the UI makes the workflow visible

### What It Does

- Coordinates multiple specialized agents for design, planning, engineering, review, and coaching.
- Organizes work around explicit artifacts such as `GDD`, `PROJECT_PLAN`, `IMPLEMENTATION_PLAN`, and `REVIEW_REPORT`.
- Provides a web workbench with project switching, settings, file views, chat, streaming feedback, and tool progress.
- Supports project-scoped workspaces, structured tool execution, and controlled file operations.
- Integrates multimodal input such as images, text files, code files, and PDFs.
- Builds toward practical engine workflows, starting with Unity and expanding to broader game-development ecosystems.

### What It Is Not

Ludens-Flow is **not** trying to fully auto-generate a complete game from one prompt.

It is a workflow system for:

- clarifying requirements
- structuring plans
- guiding implementation
- reviewing outputs
- making development steps traceable and reproducible

### Current Focus

Ludens-Flow is currently focused on:

- stabilizing the multi-agent workflow core
- improving workspace-safe tool execution
- expanding Unity-oriented engineering assistance
- polishing the workbench UX and settings flow

See [ROADMAP.md](11_docs/ROADMAP.md) for the longer-term direction.

### Quick Start

#### 1. Install

```bash
pip install -e ./agent_workbench
```

#### 2. CLI

```bash
ludensflow
```

#### 3. Web Workbench

Product mode:

```powershell
.\agent_workbench\scripts\start_web.ps1
```

Development mode:

```powershell
.\agent_workbench\scripts\start_web.ps1 -Mode dev
```

Default URLs:

- Product mode: `http://127.0.0.1:8011/`
- Dev frontend: `http://127.0.0.1:4173/`
- Dev API: `http://127.0.0.1:8011/`

### Project Structure

```text
Ludens-Flow/
├─ agent_workbench/   # core workflow engine, API, frontend, tests
├─ 11_docs/           # roadmap, design docs, long-form documentation
├─ 00_meta/           # schemas, repo rules, metadata
├─ workspace/         # runtime workspace and project data
├─ STATUS.md          # current project status snapshot
└─ README.md
```

### Screenshots

Screenshot placeholders can be added here later:

- Workbench overview
- Settings page
- Tool execution flow
- Workspace / file operation view

### Future Direction

Ludens-Flow is evolving toward a broader game-development AI workbench, including:

- stronger structured agent collaboration
- richer file and tool execution flows
- Unity editor capability integration
- broader engine compatibility such as Godot and UE
- in-game LLM integration
- collaboration platform visualization
- external AIGC ecosystem access

### Open Source

- Repository: <https://github.com/franknobox/Ludens-Flow>
- License: [MIT](LICENSE)

If you want to explore implementation details first, start with:

- [agent_workbench/README.md](agent_workbench/README.md)
- [STATUS.md](STATUS.md)
- [11_docs/ROADMAP.md](11_docs/ROADMAP.md)

> Originally initiated in the context of the 2026 SUAT AI Agent Innovation Competition, and now being shaped into a longer-lived open project.

---

## 简体中文

### Ludens-Flow 是什么？

Ludens-Flow 是一个面向游戏开发的多 Agent 工作台。它不是把大模型当成一个自由聊天助手，而是把 Agent 放回工程系统里：有项目边界、有工件、有工具权限、有状态流转，也有可以被看见和管理的工作过程。

它更关注：

- 如何澄清需求
- 如何推进策划与工程协作
- 如何让工件可追踪、可审阅、可复现
- 如何把文件、工具、工作区和前端工作台整合成一个可控系统

### 目前已经具备的方向

- 多 Agent 工作流：设计、计划、工程、评审、辅导
- 工件驱动：`GDD`、`PROJECT_PLAN`、`IMPLEMENTATION_PLAN`、`REVIEW_REPORT`
- Web 工作台：项目切换、设置页、文件视图、对话、流式反馈、工具过程展示
- 工作区与工具能力：项目级工作区、受控文件读写、工具目录
- 多模态输入：图片、文本、代码文件、PDF
- Unity 工程辅助：从只读能力逐步走向更完整的工程协作

### 它不是什么？

它不是“一个 prompt 直接生成完整游戏”的自动化系统。

它更像一个**结构化游戏开发工作台**，帮助开发者把思路、工件、实现和审阅组织起来。

### 快速开始

安装：

```bash
pip install -e ./agent_workbench
```

CLI：

```bash
ludensflow
```

Web 产品态：

```powershell
.\agent_workbench\scripts\start_web.ps1
```

Web 开发态：

```powershell
.\agent_workbench\scripts\start_web.ps1 -Mode dev
```

### 重点文档

- [Workbench 使用说明](agent_workbench/README.md)
- [项目状态](STATUS.md)
- [Roadmap](11_docs/ROADMAP.md)

### 未来方向

后续会继续推进：

- 更稳的多 Agent 协作与结构化输出
- 更完整的文件工具与执行反馈
- Unity / Godot / UE 等更多引擎兼容
- 游戏内模型能力接入
- GitHub 等协作平台可视化
- 外部 AIGC 服务统一入口

### 开源信息

- 仓库地址：<https://github.com/franknobox/Ludens-Flow>
- 开源协议：[MIT](LICENSE)

> 项目最初起步于 2026 SUAT AI Agent Innovation Competition，但当前定位是一个持续演进的开源项目。
