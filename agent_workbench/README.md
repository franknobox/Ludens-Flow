# Agent Workbench 使用指南

## 概述

Agent Workbench 是 Ludens-Flow 的多智能体工作流执行层。
它负责驱动多个专业 Agent 围绕项目工件协同推进，从需求讨论、项目规划、工程定稿到内部评审，再进入开发辅导阶段。

当前版本已经支持多项目工作台：

- 工作区根目录是 `workspace/`
- 每个项目的数据单独落在 `workspace/projects/<project_id>/`
- 首次启动时会自动创建第一个项目 `project-1`
- 如果旧版本数据还在 `workspace/` 根目录，首次启动会自动迁移到 `workspace/projects/project-1/`
- CLI 和 Web 都基于“当前项目”运行

## 快速开始

### 1. 环境配置

建议使用 Python 3.10 及以上版本。

在项目根目录准备 `.env`，至少配置一套可用的 LLM 参数：

```env
LLM_PROVIDER=openai
LLM_MODEL=moonshot-v1-auto
LLM_API_KEY=your_actual_api_key
LLM_BASE_URL=https://api.moonshot.cn/v1
LLM_TEMPERATURE=0.2
```

### 2. 安装依赖

推荐使用可编辑安装（同时安装依赖并注册 CLI 入口）：

```bash
pip install -e ./agent_workbench
```

说明：

- 安装后可直接使用 `ludensflow` 与 `ludensflow-api` 命令
- 仍可通过仓库脚本启动 Web（`start_web.ps1`）
- 可执行 `python agent_workbench/scripts/smoke_install.py` 做安装与启动 smoke 检查

## 启动方式

### 方式 A：CLI 交互模式

推荐命令：

```bash
ludensflow
```

兼容命令（老入口）：

```bash
python agent_workbench/run_agents.py
```

常用命令：

- `/projects`：列出当前工作区内的项目
- `/project new <project_id>`：创建并切换到新项目
  - `/project use <project_id>`：切换到已有项目
- `/reset` 或 `/restart`：重置当前项目状态

### 方式 B：Web 工作台

前置条件（首次机器环境）：

- 已安装 Python 3.10+（用于 FastAPI / Uvicorn）
- 已安装 Node.js 18+（用于首次构建前端）

同源产品模式：

```powershell
.\agent_workbench\scripts\start_web.ps1
```

也可显式写为：

```powershell
.\agent_workbench\scripts\start_web.ps1 -Mode product
```

访问：`http://127.0.0.1:8011/`

热更新开发模式：

```powershell
.\agent_workbench\scripts\start_web.ps1 -Mode dev
```

访问：`http://127.0.0.1:4173/`（前端）和 `http://127.0.0.1:8011/`（API）

## 工作流阶段

当前图流转包含以下主要阶段：

1. `GDD_DISCUSS / GDD_COMMIT`
   - Design Agent 负责玩法讨论和 GDD 定稿
2. `PM_DISCUSS / PM_COMMIT`
   - PM Agent 负责排期、范围收敛和项目计划定稿
3. `ENG_DISCUSS / ENG_COMMIT`
   - Engineering Agent 负责工程预设讨论和实施计划定稿
4. `REVIEW`
   - Review Agent 负责对主工件做交叉审查并生成 `REVIEW_REPORT.md`
5. `POST_REVIEW_DECISION`
   - 等待用户选择回流或进入开发辅导
6. `DEV_COACHING`
   - 主工件冻结后进入开发辅导模式

## 多项目工作区结构

当前推荐的工作区结构如下：

```text
workspace/
├── .active_project
└── projects/
    ├── project-1/
    │   ├── state.json
    │   ├── USER_PROFILE.md
    │   ├── GDD.md
    │   ├── PROJECT_PLAN.md
    │   ├── IMPLEMENTATION_PLAN.md
    │   ├── REVIEW_REPORT.md
    │   ├── logs/
    │   ├── images/
    │   ├── dev_notes/
    │   └── patches/
    └── <another_project>/
```

说明：

- `state.json`、工件、日志、用户画像都按项目隔离
- Web 工作台显示和操作的也是当前项目目录
- 项目切换不会混用别的项目状态

## 重置与清理

如果只是想重新开始当前项目：

- CLI 中输入 `/reset`
- 或在 Web 工作台点击 `Reset Current Project`

如果想手动清理：

- 删除对应项目目录下的 `state.json`
- 或直接清空整个 `workspace/projects/<project_id>/`

不再推荐使用旧的单工作区路径心智，比如直接操作 `workspace/state.json`。

## 当前实现说明

当前前端已迁移为 `Vite + React + TypeScript`（目录：`agent_workbench/web/`），并保持与原先工作台基本一致的外观与交互。

- 生产/演示模式：使用 `start_web.ps1` 默认产品态，由 FastAPI 同源托管静态资源。
- 开发联调模式：使用 `start_web.ps1 -Mode dev`，即 Vite Dev Server（默认 `4173`）+ FastAPI API（默认 `8011`）。
