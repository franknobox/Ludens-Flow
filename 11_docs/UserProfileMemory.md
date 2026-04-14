# 🎯 任务：用户画像记忆系统 (User Profile Memory)

**优先级**：P1 · **预估工时**：4~6 小时

---

## 背景与需求

我们的 4 个 AI Agent（Dam / Pax / Eon / Revs）各自只有短期对话记忆，跨阶段切换时记忆被清空。这导致用户需要反复自我介绍，Agent 之间也无法共享对用户的了解。

**需求**：新增一个共享的用户画像文件 `workspace/USER_PROFILE.md`，让所有 Agent 都能读取和提议更新，实现跨 Agent 的持久化用户记忆。

画像内容包括（暂定，先简洁一点）：用户昵称、对agent回复的偏好、项目上下文（目标/团队/时限）、以及各 Agent 的观察笔记等。

---

## 设计原则

1. **Agent 只提议，总控写入**：Agent 在回复中标记发现的新用户信息，由总控（[graph.py](file:///e:/GitDesktop/Ludens-Flow/agent_workbench/src/ludens_flow/graph.py)）统一执行文件写入，保持单写入权的架构一致性
2. **全员可读可提议**：4 个 Agent 都能读取画像、都能提交更新提议
3. **不受冻结保护影响**：画像在 DEV_COACHING 冻结期也允许更新（它不属于核心工件）
4. **控制 Token 开销**：画像内容注入 prompt 时控制在 ~500 token 以内
5. **上下文注入机制 (Context Injection)**：和现有架构中 Agent 读取前置工件（如 PM 读取 GDD 并拼接到 prompt）的原理完全一致，我们将用户画像全文本直接读取并追加到当前 Agent 的 System Prompt 尾部，不需要 RAG。
- *例子*：原 System Prompt `你是主程 Eon...` 会在运行时被临时拼接为 `你是主程 Eon... \n\n --- \n 以下是当前用户的画像...`，从而让模型自然地具备短期记忆延续的效果。

---

## 实现路径

### 第 1 步：新增画像读写模块

新建 `user_profile.py`，实现画像文件的读取、原子写入、和更新合并（去重）功能。画像不存在时自动创建带骨架的模板。

### 第 2 步：扩展 Agent 返回结构

在 [AgentResult](file:///e:/GitDesktop/Ludens-Flow/agent_workbench/src/ludens_flow/agents/base.py#19-26) 中新增 `profile_updates` 字段，用于 Agent 上报发现的用户信息。在 [BaseAgent](file:///e:/GitDesktop/Ludens-Flow/agent_workbench/src/ludens_flow/agents/base.py#28-66) 中封装一个通用解析方法，从 LLM 回复中提取 `[PROFILE_UPDATE]` 标记行。

### 第 3 步：总控对接

在 [graph.py](file:///e:/GitDesktop/Ludens-Flow/agent_workbench/src/ludens_flow/graph.py) 的 [run_agent_step()](file:///e:/GitDesktop/Ludens-Flow/agent_workbench/src/ludens_flow/graph.py#46-148) 中：

- **调用 Agent 前**：读取画像内容，注入到 Agent 的 system prompt 尾部
- **Agent 返回后**：如果有 `profile_updates`，调用画像模块执行合并写入

### 第 4 步：各 Agent Prompt 适配

在每个 Agent 的 prompt 末尾追加引导语，让 LLM 在发现新用户信息时用 `[PROFILE_UPDATE]` 格式输出。解析后从展示给用户的回复中移除这些标记。

### 第 5 步：测试

新增 `test_user_profile.py`，覆盖：空画像加载、条目追加、去重、prompt 注入、端到端更新流程。确保现有 `test_happy_path.py --skip-llm` 回归安全。

---

## 验收标准

- 新增测试全部通过
- 现有测试回归安全
- 手动验证：GDD 阶段告诉 Dam 自己的背景 → 切到 ENG 阶段后 Eon 体现出了解
- `USER_PROFILE.md` 中不包含内部标记，内容结构清晰

---

## 开始前建议先读

1. [agents/base.py](file:///e:/GitDesktop/Ludens-Flow/agent_workbench/src/ludens_flow/agents/base.py) — 了解 [AgentResult](file:///e:/GitDesktop/Ludens-Flow/agent_workbench/src/ludens_flow/agents/base.py#19-26) 返回结构
2. [graph.py](file:///e:/GitDesktop/Ludens-Flow/agent_workbench/src/ludens_flow/graph.py) 的 [run_agent_step()](file:///e:/GitDesktop/Ludens-Flow/agent_workbench/src/ludens_flow/graph.py#46-148) — 了解总控如何处理 Agent 返回值
3. [artifacts.py](file:///e:/GitDesktop/Ludens-Flow/agent_workbench/tests/test_artifacts.py) — 参考工件写入的设计范式
4. 任意一个 Agent 文件 — 了解 prompt 拼装方式
