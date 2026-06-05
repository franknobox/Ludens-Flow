<p align="center">
  <img src="11_docs/IMAGE/LF.svg" alt="Ludens-Flow logo" width="96" />
</p>

<p align="center">
  <strong>An agent-native workbench for structured game development.</strong>
</p>

<p align="center">
  <strong>English</strong> ·
  <a href="README.zh.md">简体中文</a>
</p>

<p align="center">
  <a href="https://github.com/franknobox/Ludens-Flow">GitHub</a> ·
  <a href="agent_workbench/README.md">Workbench Docs</a> ·
  <a href="LICENSE">MIT License</a>
</p>

---

## What Is Ludens-Flow?

Ludens-Flow is a human-in-the-loop, multi-agent game development workbench built around explicit artifacts, controlled tools, and project-level state.

It is designed to help teams and solo developers structure game development work, not just chat with a model or hand over the whole project to an opaque automation loop.

Instead of treating the agent as a free-form assistant, Ludens-Flow puts it back inside an engineering system:

- services have boundaries
- outputs have schemas
- tools have permissions
- tasks have state
- projects have workspaces
- the UI keeps the workflow visible
- users can inspect, edit, approve, export, or override important steps

## What It Does

- Coordinates multiple specialized agents for design, planning, engineering, review, and coaching.
- Organizes work around explicit artifacts such as `GDD`, `PROJECT_PLAN`, `IMPLEMENTATION_PLAN`, and `REVIEW_REPORT`.
- Provides a web workbench with project switching, settings, file views, chat, streaming feedback, and tool progress.
- Supports project-scoped workspaces, structured tool execution, and controlled file operations.
- Integrates multimodal input such as images, text files, code files, and PDFs.
- Supports project profiles and externally imported Skills that can be enabled per project.
- Connects external game engines through a controlled MCP capability layer, with Unreal MCP integration being actively connected and validated.
- Provides a copywriting workspace with external references, live generation status, and Markdown/CSV export.
- Provides an AIGC shortcut directory for game-production image, audio, video, 3D, UI, and reference workflows.
- Provides a Game AI Config Center for designing in-game AI scenes, model/provider configs, prompt/tool combinations, test calls, and exportable integration packages.
- Integrates Level Layout Studio / 关卡设计台 as a local offline level layout tool with import/export support, autosave, and Ludens-Flow-specific interaction fixes.
- Supports capability-aware model routing with per-project configuration.
- Offers a resilient web workbench with real-time streaming, thinking/progress flow, tool progress tracking, and multi-theme support.

## What It Is Not

Ludens-Flow is **not** trying to fully auto-generate a complete game from one prompt.

It is a workflow system for:

- clarifying requirements
- structuring plans
- guiding implementation
- reviewing outputs
- making development steps traceable and reproducible

## Current Focus

Ludens-Flow is currently focused on:

- stabilizing the multi-agent workflow core, backend API structure, and endpoint coverage
- connecting real game engines via MCP for live asset, scene, editor, and log operations, with Unreal as the current active integration target
- improving the Game AI Config Center so users can configure, test, export, and understand practical in-game AI workflows
- expanding project tools such as AIGC entry points, copywriting export, model routing, and Level Layout Studio into coherent project workflows
- hardening project-level state persistence, metadata safety, workspace isolation, and browser-side recovery behavior
- improving the web workbench browsing experience, observability, settings management, dark/light themes, and responsive UX

See [ROADMAP.md](11_docs/ROADMAP.md) for the longer-term direction.

## Sponsor

<p align="center">
  <img src="11_docs\IMAGE\mimo.png" alt="Xiaomi MiMO logo" width="360" />
</p>

Ludens-Flow receives token support from **Xiaomi MiMO**.

## Quick Start

#### 1. Install

```bash
pip install -e ./agent_workbench
```

#### 2. Web Workbench

Product mode:

```powershell
.\agent_workbench\scripts\start_web.ps1
```

Default URLs:

- Product mode: `http://127.0.0.1:8011/`

CLI note: the `ludensflow` command is a legacy/debug entry for now and is not the recommended way to run the project.

## Project Structure

```text
Ludens-Flow/
├─ agent_workbench/   # core workflow engine, grouped FastAPI API, frontend, tests
├─ 11_docs/           # roadmap, design docs, long-form documentation
├─ 00_meta/           # schemas, repo rules, metadata
├─ workspace/         # runtime workspace and project data
├─ STATUS.md          # current project status snapshot
└─ README.md
```

## Screenshots

Screenshot placeholders can be added here later:

- Workbench overview
- Settings page
- Tool execution flow
- Workspace / file operation view

## Future Direction

Ludens-Flow is evolving toward a broader game-development AI workbench, including:

- deeper engine integration through MCP, including Unreal editor operations, output-log reading, PIE control, viewport/context capture, and project-side validation
- agent-driven module automation, where the user can describe a goal and the agent can operate workbench modules such as copywriting, AIGC, MCP, model configuration, and layout tools under explicit permission
- practical in-game AI integration: configuration JSON, example code, usage guides, model routing, streaming output, tool-call audit, cache, rate limits, cost budgets, and fallback policies
- Level Layout Studio evolution into a first-class local level-design workspace, with Agent-assisted layout generation and project result return
- stronger multimodal workflows covering voice, image, video, UI references, world-model exploration, and generated game assets
- smoother external AIGC loops: choose a capability inside Ludens-Flow, jump to or call an external service, then bring results back into the project workflow
- stronger structured agent collaboration with role-based communication protocols, traceable decisions, and human review checkpoints
- release acceptance baselines, browser smoke tests, and repeatable workflow evaluation

## Open Source

- Repository: <https://github.com/franknobox/Ludens-Flow>
- License: [MIT](LICENSE)

If you want to explore implementation details first, start with:

- [agent_workbench/README.md](agent_workbench/README.md)
- [STATUS.md](STATUS.md)
- [11_docs/ROADMAP.md](11_docs/ROADMAP.md)

> Originally initiated in the context of the 2026 SUAT AI Agent Innovation Competition, and now being shaped into a longer-lived open project.
