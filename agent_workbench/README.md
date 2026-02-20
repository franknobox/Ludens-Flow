# Agent Workbench 使用指南

## 📋 概述

Agent Workbench 是 Ludens-Flow 的核心执行引擎,通过多智能体协作生成游戏开发工件。

## 🚀 快速开始

### 1️⃣ 环境配置

```bash
# 在项目根目录下复制环境变量模板
cp .env.example .env
```

编辑 `.env` 文件,配置你的 LLM API:

```env
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
LLM_API_KEY=your_actual_api_key
LLM_BASE_URL=  # 可选,用于兼容OpenAI接口的其他服务
LLM_TEMPERATURE=0.2
```

**支持的 LLM 提供商:**
- OpenAI (官方)
- Moonshot AI (Kimi) - 设置 `base_url=https://api.moonshot.cn/v1`
- DeepSeek - 设置相应的 `base_url`
- 其他 OpenAI 兼容接口

### 2️⃣ 安装依赖

```bash
pip install openai python-dotenv
```

### 3️⃣ 运行基线流程

**从项目根目录运行:**

```bash
python agent_workbench/run_baseline.py
```

**或者进入 agent_workbench 目录:**

```bash
cd agent_workbench
python run_baseline.py
```

## 📦 输出工件

成功运行后,会在 `artifacts/` 目录下生成以下文件:

```
artifacts/
├── gdd/GDD.md                          # 游戏设计文档
├── pm/PROJECT_PLAN.md                  # 项目计划
├── coding/IMPLEMENTATION_PLAN.md       # 实现计划
└── review/REVIEW_REPORT.md             # 审查报告
```

## 🔄 工作流程

```
用户需求 → Design Agent → PM Agent → Engineering Agent → Review Agent → 输出工件
```

1. **Design Agent**: 生成游戏设计文档 (GDD)
2. **PM Agent**: 根据 GDD 制定项目计划
3. **Engineering Agent**: 输出技术实现计划
4. **Review Agent**: 对所有工件进行审查评估

## ⚙️ 自定义需求

编辑 `run_baseline.py` 中的 `user_request` 变量:

```python
user_request = (
    "基于Unity6引擎,我希望制作一款赛博朋克题材的2D俯视角关卡制游戏,核心是暗杀与送货;"
    "强调潜行、路线规划、轻量战斗;每关有不同目标与撤离点。"
)
```

## 🛠️ 故障排除

**问题: `can't open file 'run_baseline.py'`**
- 确保从正确的目录运行,或使用完整路径: `python agent_workbench/run_baseline.py`

**问题: `Missing env var: LLM_API_KEY`**
- 检查 `.env` 文件是否在项目根目录
- 确认 `LLM_API_KEY` 已正确配置

**问题: API 调用失败**
- 验证 API Key 是否有效
- 检查 `LLM_BASE_URL` 是否正确(如使用第三方服务)
- 确认网络连接正常