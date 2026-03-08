# Ludens-Flow 技术文档（竞赛版）

## 1. 文档信息

- 项目名称：Ludens-Flow
- 文档类型：技术架构与实现规范
- 适用场景：高校 Agent 创新开发大赛技术材料
- 版本：v1.0（基于当前 `dev` 工作分支代码）
- 更新时间：2026-03-08

---

## 2. 项目概述

Ludens-Flow 是一个面向游戏研发前期流程的多 Agent 协作系统。项目核心目标不是“自动生成完整游戏”，而是将立项阶段的关键活动（策划、排期、工程架构、评审）结构化、可追踪化、可复盘化。

系统以“工件（Artifact）”为中心，围绕以下四类主工件展开协作：

- `GDD.md`：游戏设计文档
- `PROJECT_PLAN.md`：项目计划文档
- `IMPLEMENTATION_PLAN.md`：工程实现方案
- `REVIEW_REPORT.md`：评审报告与 Gate 结果

---

## 3. 设计目标与边界

### 3.1 设计目标

1. 建立可控的多 Agent 流程状态机，避免“无边界聊天”。
2. 保证核心文档写入具有明确责任主体（单写入权限）。
3. 支持回流修订（Review 后可回到 GDD/PM/ENG）。
4. 支持冻结期开发辅导（DEV_COACHING）与变更隔离。
5. 支持可选的联网搜索能力与多模态图片输入。

### 3.2 非目标

1. 不直接产出可运行游戏包。
2. 不承担 CI/CD、发布、商业化运营等全生命周期能力。
3. 不内置复杂前端协作平台（当前以 CLI 为主）。

---

## 4. 总体架构

### 4.1 架构分层

系统采用“状态机驱动 + Agent 执行 + 工件治理”三层协作模型：

1. 控制层（Router）
- 文件：`agent_workbench/src/ludens_flow/router.py`
- 职责：状态转移决策、用户意图解析、回流策略、冻结控制、迭代次数保护。

2. 编排层（Graph）
- 文件：`agent_workbench/src/ludens_flow/graph.py`
- 职责：将 Router 结果映射到对应 Agent 节点，并统一执行 `discuss/commit/coach` 生命周期。

3. 领域层（Agents + Artifacts + State）
- Agent：`agent_workbench/src/ludens_flow/agents/*.py`
- 工件治理：`agent_workbench/src/ludens_flow/artifacts.py`
- 全局状态：`agent_workbench/src/ludens_flow/state.py`

### 4.2 运行入口

- CLI 入口：`agent_workbench/run_agents.py`
- 主循环职责：
  - 初始化 workspace
  - 加载/保存 state
  - 解析用户输入（文本/图片）
  - 驱动 `graph_step(state, user_input)`
  - 支持 `/reset` 与 `/restart`

---

## 5. 状态机规范

### 5.1 Phase 定义

`router.py` 中定义了 9 个阶段：

1. `GDD_DISCUSS`
2. `GDD_COMMIT`
3. `PM_DISCUSS`
4. `PM_COMMIT`
5. `ENG_DISCUSS`
6. `ENG_COMMIT`
7. `REVIEW`
8. `POST_REVIEW_DECISION`
9. `DEV_COACHING`

### 5.2 标准主路径

`GDD_DISCUSS -> GDD_COMMIT -> PM_DISCUSS -> PM_COMMIT -> ENG_DISCUSS -> ENG_COMMIT -> REVIEW -> POST_REVIEW_DECISION -> DEV_COACHING`

### 5.3 回流机制（Review Gate）

Review 完成后由用户做 A/B/C 决策：

- A：按 Gate `targets` 回流到目标阶段（全量修复）
- B：仅针对 `BLOCK/MAJOR` 问题回流（若无严重问题可直接放行）
- C：强制进入 `DEV_COACHING` 并冻结主工件

### 5.4 冻结机制

进入 `DEV_COACHING` 后 `artifact_frozen=True`，主工件禁止覆写。用户仍可进行技术问答，且可通过“解冻”意图触发新一轮迭代回到 `ENG_DISCUSS`。

### 5.5 保护机制

1. 迭代上限保护：`iteration_count > max_iterations` 时强制进入 `DEV_COACHING`。
2. 路由日志记录：每次迁移写入 `workspace/logs/router.log`。
3. 节点执行日志：每次 Agent 执行写入 `workspace/logs/trace.log`。

---

## 6. Agent 体系设计

### 6.1 BaseAgent 抽象

文件：`agent_workbench/src/ludens_flow/agents/base.py`

统一返回结构：

- `AgentResult.assistant_message`：面向用户显示的回复
- `AgentResult.state_updates`：增量状态更新（drafts、review_gate 等）
- `AgentResult.commit`：可选 `CommitSpec`，仅在提交阶段返回
- `AgentResult.events`：流程事件（如 `GDD_COMMITTED`）

### 6.2 四类业务 Agent

1. `DesignAgent`
- 职责：GDD 讨论与固化。
- 输出工件：`GDD.md`。

2. `PMAgent`
- 职责：排期、里程碑、任务分解、MVP 收敛。
- 输出工件：`PROJECT_PLAN.md`。
- 支持从文本中抽取结构化 `ChangeRequest`。

3. `EngineeringAgent`
- 职责：工程架构讨论、实现计划提交、开发教练模式。
- 输出工件：`IMPLEMENTATION_PLAN.md`（提交阶段）。
- 辅助能力：支持工具调用（Web Search）。

4. `ReviewAgent`
- 职责：跨文档一致性审查，生成评审报告与 Gate JSON。
- 输出工件：`REVIEW_REPORT.md`。
- 规则熔断：发现 `BLOCK` 或低分自动降级为 `REQUEST_CHANGES/BLOCK`。

---

## 7. 工件治理机制

文件：`agent_workbench/src/ludens_flow/artifacts.py`

### 7.1 关键机制

1. 注册表机制（Artifact Registry）
- 为每个工件绑定路径和唯一 owner（如 `GDD -> DesignAgent`）。

2. 单写入权限
- `write_artifact` 校验 `actor == owner`，否则拒绝写入。

3. 冻结保护
- `artifact_frozen=True` 时禁止改写 canonical 工件（除豁免项外）。

4. 原子写入
- 使用临时文件 + `os.replace`，避免中断导致工件损坏。

5. 版本与哈希追踪
- 每次提交更新 `version/hash/updated_at/reason`，并落盘日志。

### 7.2 冻结期替代写入通道

- `write_dev_note(...)` -> `workspace/dev_notes/`
- `write_patch(...)` -> `workspace/patches/`

目的：允许持续协作，不破坏主基线工件。

---

## 8. 状态与存储规范

### 8.1 状态结构

文件：`agent_workbench/src/ludens_flow/state.py`

核心字段：

- 流程控制：`phase / iteration_count / max_iterations / artifact_frozen`
- 上下文：`style_preset`
- 过程数据：`drafts / change_requests / decisions / review_gate`
- 对话缓存：`chat_history`
- 工件元数据：`artifacts`

### 8.2 路径治理

文件：`agent_workbench/src/ludens_flow/paths.py`

- 统一根目录：`workspace/`（可通过 `LUDENS_WORKSPACE_DIR` 覆盖）
- 标准子目录：
  - `logs/`
  - `memory/`
  - `images/`
  - `dev_notes/`
  - `patches/`

### 8.3 重置策略

- CLI 输入 `/reset` 或 `/restart`：
  - 删除 `state.json`
  - 清空 `workspace/images`（保留目录）
  - 加载全新初始状态

---

## 9. 多模态与联网能力

### 9.1 图片输入能力

文件：`agent_workbench/run_agents.py`

处理流程：

1. 识别输入中的本地图片路径（`png/jpg/jpeg/webp`）。
2. 优先使用 Pillow 压缩/缩放为较小 JPEG（控制 token 成本）。
3. 转换为 `data:image/...;base64,...` 并组装多模态 payload。
4. 若无 Pillow，则退化为原图读取（并给出告警）。

### 9.2 联网搜索能力

文件：`agent_workbench/src/ludens_flow/tools/search.py`

- 使用 `ddgs` 执行 DuckDuckGo 文本搜索。
- 通过标准 Tool Schema 暴露给 LLM 调用。
- 依赖缺失时自动降级：返回“搜索不可用”而不影响主流程。

---

## 10. LLM 适配层设计

文件：`agent_workbench/llm/provider.py`

### 10.1 配置模型

- `LLM_PROVIDER`（当前主要为 OpenAI 兼容接口）
- `LLM_MODEL`
- `LLM_API_KEY`
- `LLM_BASE_URL`
- `LLM_TEMPERATURE`

### 10.2 兼容策略

1. 对推理模型（如 `o1/o3/k2.5`）避免强行设置采样参数。
2. 若接口因 `temperature/top_p` 报错，自动移除并重试。
3. 支持 Tool Calling 回路，由 `BaseAgent._call` 统一处理。

---

## 11. 日志与可观测性

### 11.1 日志文件

- `workspace/logs/trace.log`：节点级 Enter/Leave、提交标记、错误信息
- `workspace/logs/router.log`：路由迁移、原因、Gate 状态、迭代信息
- `workspace/logs/artifacts.log`：工件版本变更追踪

### 11.2 可追踪价值

1. 可复盘每次状态迁移决策。
2. 可定位是哪一阶段导致回流。
3. 可审计每个工件由谁、何时、为何更新。

---

## 12. 测试策略

测试目录：`agent_workbench/tests/`

### 12.1 覆盖范围（当前）

1. 状态机路由与选项解析：
- `test_router.py`
- `test_router_options.py`
- `test_router_v2.py`

2. 图引擎与冻结保护：
- `test_step5_graph_engine.py`
- `test_freeze.py`

3. Happy Path（含可选真实 LLM）：
- `test_happy_path.py`

4. 工件权限与写入机制：
- `test_artifacts.py`

5. 工具与多模态输入：
- `test_tools.py`

6. Workspace 重置行为（含 images 清理）：
- `test_workspace_reset.py`

### 12.2 测试特征

1. 多数测试使用临时工作目录，避免污染真实 workspace。
2. 支持 Mock 与真实调用双模式（真实网络测试可按环境变量控制）。
3. 强调流程正确性、权限边界与异常恢复。

---

## 13. 依赖与运行规范

### 13.1 依赖列表

根目录 `requirements.txt`：

- `openai>=1.0.0`
- `python-dotenv>=1.0.0`
- `ddgs>=9.11.2`
- `Pillow>=10.0.0`

### 13.2 启动方式

```bash
python agent_workbench/run_agents.py
```

### 13.3 关键环境变量

```env
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
LLM_API_KEY=...
LLM_BASE_URL=...
LLM_TEMPERATURE=0.2
LUDENS_WORKSPACE_DIR=./workspace   # 可选
```

---

## 14. 工程优势（竞赛视角）

1. **流程可控**：显式状态机与 Gate 决策，避免 Agent 漫游。
2. **治理清晰**：工件单写权限 + 原子写入 + 冻结保护。
3. **可审计**：决策、工件、执行均有日志链路。
4. **可扩展**：Agent/tool/path 设计支持增量接入新能力。
5. **可实战**：已具备多模态输入与可选联网能力，适合工程化展示。

---

## 15. 当前风险与改进方向

### 15.1 已识别风险

1. 依赖 LLM 输出格式稳定性（尤其 Review JSON 解析）。
2. 某些测试仍偏脚本式，统一到 `pytest` 体系可提升 CI 质量。
3. CLI 入口较强，前后端协议层尚未抽象为独立 API。

### 15.2 建议迭代

1. 引入 JSON Schema 强约束输出并做自动校验。
2. 将 Router 与 Graph 的协议抽象为服务层 API，方便前端直连。
3. 增加回放工具（Replay）用于比赛现场演示与问题复现。

---

## 16. 附录：关键文件索引

- 运行入口：`agent_workbench/run_agents.py`
- 状态机：`agent_workbench/src/ludens_flow/router.py`
- 图执行：`agent_workbench/src/ludens_flow/graph.py`
- 状态持久化：`agent_workbench/src/ludens_flow/state.py`
- 路径管理：`agent_workbench/src/ludens_flow/paths.py`
- 工件治理：`agent_workbench/src/ludens_flow/artifacts.py`
- Agent 抽象：`agent_workbench/src/ludens_flow/agents/base.py`
- 业务 Agent：
  - `agent_workbench/src/ludens_flow/agents/design_agent.py`
  - `agent_workbench/src/ludens_flow/agents/pm_agent.py`
  - `agent_workbench/src/ludens_flow/agents/engineering_agent.py`
  - `agent_workbench/src/ludens_flow/agents/review_agent.py`
- 搜索工具：`agent_workbench/src/ludens_flow/tools/search.py`
- LLM 适配：`agent_workbench/llm/provider.py`
- 测试目录：`agent_workbench/tests/`

