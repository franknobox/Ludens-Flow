# Agent Workbench 使用指南

## 概述

Agent Workbench 是 Ludens-Flow 的多智能体工作流执行层。
它负责驱动多个专业 Agent 围绕项目工件协同推进，从需求讨论、项目规划、工程定稿到内部评审，再进入开发辅导阶段。

当前版本已经支持多项目工作台：

- 工作区根目录是 `workspace/`
- 每个项目的数据单独落在 `workspace/projects/<project_id>/`
- 外部 Skills 全局安装在 `workspace/skills/installed/<skill_id>/`，项目只保存启用关系
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

说明：

- `.env` 仍是全局保底模型配置。
- 当项目未配置模型路由时，所有 Agent 默认回退到 `.env`。
- 部分 provider 支持专用密钥环境变量（如 `OPENAI_API_KEY`、`OPENROUTER_API_KEY`、`DEEPSEEK_API_KEY`、`GROQ_API_KEY`、`TOGETHER_API_KEY`、`XAI_API_KEY`、`OLLAMA_API_KEY`）。

如果需要在 Web 设置页里给不同 Agent 选择不同 provider，可以额外配置 Provider Profile。真实 key 仍然放在独立环境变量里，Profile 只引用 key 的变量名：

```env
OPENAI_API_KEY=your_openai_key
DEEPSEEK_API_KEY=your_deepseek_key
LUDENS_MODEL_PROFILES={"openai_main":{"provider":"openai","base_url":"https://api.openai.com/v1","api_key_env":"OPENAI_API_KEY"},"deepseek_main":{"provider":"openai_compatible","base_url":"https://api.deepseek.com/v1","api_key_env":"DEEPSEEK_API_KEY"}}
```

### 1.1 多模型路由配置（项目级）

当前已支持按项目配置不同 Agent / 不同能力使用不同模型，推荐在 Web 设置页进行维护：

- 进入 `设置 -> 通用设置 -> 模型路由`
- 选择 Provider Profile、模型和温度后保存

优先级规则：

`agent_capabilities > capabilities > agents > global > .env`

示例：

```json
{
  "agents": {
    "design": { "profile": "openai_main", "model": "gpt-4o" },
    "review": { "profile": "openai_main", "model": "o4-mini" }
  },
  "agent_capabilities": {
    "design": {
      "copywriting": { "profile": "deepseek_main", "model": "deepseek-chat", "temperature": 0.7 }
    }
  }
}
```

也可通过 API 更新：`POST /api/projects/current/settings`（字段：`model_routing`）。

### 1.2 用户画像与 Skills

当前项目的用户画像文件位于：

```text
workspace/projects/<project_id>/USER_PROFILE.md
```

可以在 Web 设置页的 `用户画像` 中直接查看、编辑和保存。Agent 在涉及用户身份、偏好、项目目标和约束时会读取该文件作为上下文。

外部 Skills 使用全局安装、项目启用的方式管理：

```text
workspace/skills/installed/<skill_id>/
├── skill.json
└── prompt.md
```

可以在 Web 设置页的 `Skills` 中导入、删除和管理 Skill，并在工作台的 Skills 页面为当前项目启用或关闭。当前阶段已完成外部导入与项目级开关；已启用 Skill 接入 Agent 运行时加载仍在后续开发中。

### 2. 安装依赖

推荐使用可编辑安装（安装后端依赖，并注册调试入口）：

```bash
pip install -e ./agent_workbench
```

说明：

- 当前推荐通过仓库脚本启动 Web（`start_web.ps1`）
- `ludensflow` CLI 目前作为旧版/调试入口保留，暂不作为推荐启动方式
- `ludensflow-api` 可作为后端 API 调试入口使用
- 可执行 `python agent_workbench/scripts/smoke_install.py` 做安装与启动 smoke 检查

## 启动方式

### 方式 A：Web 工作台（推荐）

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

### 方式 B：CLI 交互模式（旧版/调试）

CLI 入口目前保留用于兼容和调试，不作为推荐启动方式：

```bash
ludensflow
```

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

## MCP 引擎接入

当前已支持通过 MCP（Model Context Protocol）连接外部游戏引擎。连接配置内置在前端，可直接在 Web 工作台操作：

- 进入 `设置 -> 引擎连接`，添加或编辑 MCP 连接（如 Blender、Unity、Godot、Unreal）。
- 连接配置按项目持久化，保存在对应项目的元数据中。

已实机验证的能力（Blender）：

- `engine_list_scene`：列出当前场景中的对象
- `engine_create_object`：在场景中创建对象
- `engine_save_scene`：保存场景文件

其他引擎（Unity / Godot / Unreal）当前采用安全沙箱校验：写入类操作限定在项目可写工作区内，并对脚本扩展名、运行模式等做白名单检查。

安全与行为说明：

- **写操作权限确认**：MCP 工具执行涉及写入时，前端会弹出权限确认；如果未配置权限处理器或用户未明确允许，写入会被拒绝（fail-closed）。
- **健康检查 TTL 缓存**：MCP 连接的健康检查带 30 秒 TTL 缓存，避免短时间内重复启动外部进程。
- **工具事件可观测**：Agent 调用工具时，前端会实时展示工具进度事件；历史消息中也会汇总展示已执行的工具名称与次数。

## Agent Workbench 目录结构

```text
agent_workbench/
├── pyproject.toml          # Python 包配置与依赖
├── README.md               # 本文件
├── prompts/                # Agent 提示词模板
├── scripts/                # 启动与辅助脚本
│   ├── start_web.ps1
│   └── smoke_install.py
├── src/                    # 后端源码
│   ├── ludens_flow/        # 主包
│   │   ├── app/            # FastAPI 应用入口与 api/ 分组路由
│   │   ├── capabilities/   # 能力模块
│   │   │   ├── artifacts/  # 工件读写管理
│   │   │   ├── copywriting/# 文案生成能力
│   │   │   ├── github/     # GitHub 集成
│   │   │   ├── ingest/     # 文件摄取
│   │   │   ├── mcp/        # MCP 引擎接入
│   │   │   │   └── adapters/  # 各引擎适配器
│   │   │   ├── skills/     # Skills 管理
│   │   │   ├── tools/      # 工具注册与分发
│   │   │   └── workspaces/ # 工作区工具
│   │   └── core/           # 核心引擎
│   │       ├── agents/     # Agent 基类与各专业实现
│   │       ├── schemas/    # 数据模型与校验
│   │       └── state/      # 状态存储与持久化
│   └── llm/                # LLM 客户端封装
├── tests/                  # 测试套件
└── web/                    # 前端（Vite + React + TypeScript）
    ├── src/
    │   ├── features/       # 功能模块
    │   │   ├── aigc/       # AIGC 快捷入口
    │   │   ├── copywriting/# 文案加工台
    │   │   ├── game-model/ # Game Model 页面
    │   │   ├── github/     # GitHub 可视化
    │   │   ├── mcp/        # MCP 引擎连接页面
    │   │   ├── settings/   # 设置页
    │   │   ├── skills/     # Skills 管理
    │   │   ├── welcome/    # 欢迎页
    │   │   └── workbench/  # 主工作台（对话、工件、工具事件）
    │   └── styles/         # 主题与样式
    └── ...
```

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
