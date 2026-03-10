# Agent Workbench 使用指南 (Ludens Flow V2)

## 📋 概述

Agent Workbench 是 Ludens-Flow 的核心多智能体工作流引擎。在这里，用户可以与多位专业的 AI Agent 沉浸式互动交谈，从想法萌芽到架构敲定，完整模拟游戏开发前期的核心立项全流程。

## 🚀 快速开始

### 1️⃣ 环境配置

请确保你的电脑上安装了 Python（建议 3.8+）。
在**项目根目录**下，准备/创建环境变量文件 `.env`，配置你所使用的 LLM API：

```env
LLM_PROVIDER=openai
LLM_MODEL=moonshot-v1-auto
LLM_API_KEY=your_actual_api_key
LLM_BASE_URL=https://api.moonshot.cn/v1  # 根据您具体服务商的网关填写
LLM_TEMPERATURE=0.2
```

### 2️⃣ 安装轻量级依赖

本工作流采用极为轻量的原生架构实现，绝无冗杂笨重的第三方依赖，仅需安装两个通信读写库：

```bash
pip install openai python-dotenv
```

### 3️⃣ 启动方式

**方式 A：交互式终端**

在**项目根目录**运行：

```bash
python agent_workbench/run_agents.py
```

**方式 B：飞书风格 Web 前端**

在**项目根目录**安装 Web 依赖并启动 API 服务：

```bash
pip install fastapi "uvicorn[standard]"

uvicorn agent_workbench.api:app --reload
```

浏览器访问 **http://127.0.0.1:8000/** 即可使用。

## 🔄 核心阶段与智能体矩阵

整个流转图（Graph）涵盖了五大阶段，每个防区均由专职的 Agent 把守：

1. **GDD_DISCUSS / GDD_COMMIT (Design Agent)**
   - 系统游戏策划。它会引导与你探讨核心循环、MVP 范围等，最终撰写极具落地度的 `GDD.md`。
2. **PM_DISCUSS / PM_COMMIT (PM Agent)**
   - 资深项目经理。根据 GDD 抓取核心功能模块并进行开发路线图排期，输出包含开发周期及人力分配的 `PROJECT_PLAN.md`。
3. **ENG_DISCUSS / ENG_COMMIT (Engineering Agent)**
   - 技术合伙人与主程。同你敲定工程架构与代码规范预设（包含 A/B/C 三选一风格），并梳理面向具体引擎的实操级核心技术单 `IMPLEMENTATION_PLAN.md`。
4. **REVIEW_GATE (Review Agent)**
   - 无情的验收门神。对前三份文档进行交叉对比与打分（Design 与 Eng 分值需同时 ≥ 6，且不存在 Block 级隐患），一旦发现数据脱节或技术死胡同，将无情打回重做。最终生成点评表 `REVIEW_REPORT.md`。
5. **DEV_COACHING (Engineering Coach)**
   - **无限流转探讨模式**。一旦四大主文件均通过门神并“结冰”定稿，主程 Agent 将化身永远在线的技术私教。随时向它请教引擎实操解惑，也可索要能够复制喂给下等 Coding Copilot Agent (即 Cursor 等IDE) 的保姆级 Code Prompt 指令段。

## 📦 存档体系与本地工件

工作流的所有状态、草稿提取与结果呈现均会保存于 `workspace/` 目录下（且全盘通过严谨的正则提取免除了额外的 json 脏数据）：

```text
workspace/
├── state.json                  # 全局状态树记录了系统当前的流转指针、对话记录和 JSON 更新槽
├── GDD.md                      # 游戏设计文档 (Design Agent 产出)
├── PROJECT_PLAN.md             # 项目排期与实现路线图 (PM Agent 产出)
├── IMPLEMENTATION_PLAN.md      # 架构建议与系统任务单 (Engineering Agent 产出)
└── REVIEW_REPORT.md            # 综合维度评审报告单 (Review Agent 产出)
```

> **💡 贴士：如何重新开始（清除记忆）？**  
> 如果想重置整个多智能体系统的会话状态，开启下一个项目的头脑风暴，只需在终端交互时输入 `/reset` 或 `/restart` 指令，系统将自动清除状态并回到最初阶段。你也可以手动删除 `workspace/state.json` 文件后重启启动脚本来完美清零。