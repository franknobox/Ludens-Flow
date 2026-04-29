System Design Document (V1)
本文为 Ludens-Flow 项目的第一版系统设计案（V1），
 目标是在不引入过度实现细节的前提下，明确系统边界、Agent 职责与 Pipeline 行为，
 为工程执行阶段提供清晰、无歧义的设计依据。

---
1. Project Goal & Scope
1.1 Project Goal
Ludens-Flow 是一个面向游戏开发流程的多智能体辅助系统，
 以 流程编排（pipeline）+ 结构化工件（artifact-centric） 为核心设计思想。
本项目的目标是：
构建一个能够稳定跑通
策划 → 项目管理 → 实现规划 → 评审
 的系统级 Demo，而非生成完整可玩的游戏产品。
【在此补充：项目的主要应用场景 / 使用对象 / 示例输入】

---
2. System Overview
2.1 High-level Architecture
Ludens-Flow 采用编排式多智能体结构，由多个职责清晰的 Agent 按固定顺序协作完成任务。
系统整体流程如下：
User Input
   ↓
Design Agent
   ↓
PM Agent
   ↓
Engineering Agent
   ↓
Review Agent
   ↳ (Fail) → Engineering Agent (Revise)
   ↳ (Pass) → Final Output
【可选：后续补充架构图 / 时序图】

---
2.2 Producer / Workflow Orchestrator
Producer 并非内容生成 Agent，而是系统控制层，负责：
- Pipeline 顺序编排
- 状态管理（project state）
- 条件判断与回退逻辑
- 流程终止与完成判定
Producer 的目标是保证系统可回放、可解释、可复现。

---
3. Agent Roles & Boundaries
本节定义 Agent 的系统级行为契约，
 不涉及 prompt、模型或内部实现细节。

---
3.1 Design Agent（策划 Agent）
System Role
 Design Agent 负责将用户的高层需求转化为结构化的游戏设计方案，
 作为后续所有规划与实现的唯一设计输入来源。
Input
- 用户需求描述
- 项目约束（如平台、规模、周期）
测试例：赛博朋克题材的 2D 俯视角关卡制暗杀+送货游戏。整体结构以手工设计的关卡地图 + 任务驱动推进为核心，玩家通过进入关卡、完成明确目标来推进流程。游戏包含一定的战斗与环境交互（解谜）元素，但暂不引入build系统，有一定的RPG性质，更多体现在任务、世界观、叙事和表达风格上，而非复杂系统。叙事采用轻文本 + 少量 NPC + 场景与任务结合的方式。
Output
- gdd.md（或等价命名）
  一份详细的策划案，初版可以先让AI设计Schema，后面我再优化
【此处可补充：Design 文档的核心章节结构】

---
3.2 PM Agent（项目管理 Agent）
System Role
 PM Agent 负责将设计方案转化为可执行的项目管理计划，
 明确开发阶段、任务拆解与协作约定。
Input
- gdd.md
Output
- project_plan.md
  - 开发阶段与里程碑
  - 任务拆解
  - 协作方式与目录结构建议
  可以先这样

---
3.3 Engineering Agent（工程 Agent）
System Role
 Engineering Agent 负责在设计与项目计划的基础上，
 生成工程实现路径与任务级实现建议，辅助开发者进行编码。
Input
- gdd.md
- project_plan.md
Output
- implementation_plan.md
  - 实现里程碑
  - 任务级拆解
  - 伪代码 / 接口级建议
可以说的更像人话一些

---
3.4 Review Agent（评审 Agent）
System Role
 Review Agent 负责基于预定义规则，对当前方案进行一致性、可行性与完整性评审，
 并决定流程是否可以继续。
Input
- 当前版本的系统工件（Design / Plan / Implementation）
就是以上的文件
Output
- review_report.md
  - 是否通过（Pass / Fail）
  - 问题列表与风险说明
先这样

---
4. Core Artifacts
系统中的核心工件包括但不限于：
暂时无法在飞书文档外展示此内容
【可补充：命名规范 / 目录位置】

---
5. Pipeline Rules (V1)
5.1 Execution Rules
- Agent 输出在成功落盘后，视为该阶段完成
- 所有核心工件采用 全量覆盖写入策略
- 系统同一会话只保留最新版本工件
就是说，这些产出文件要存在一个地方，可以单独打开看
是否可以多轮对话，回滚重写覆盖，视情况而定

---
5.2 Control & Fallback Rules 先不搞这个
- Review Agent 输出为 Fail 时：
  - 系统回退至 Engineering Agent
  - 触发重写流程
- 若关键输入缺失：
  - Pipeline 中止
  - 返回错误说明
【可补充：最大重试次数 / 中止条件】

---
6. Definition of Done (V1)
本项目在满足以下条件时，视为 V1 阶段完成：
- Pipeline 可一键运行
- Design → PM → Engineering → Review 全流程至少稳定跑通 1 次
- 输出结果结构清晰、可解释、可复现
- 不依赖人工临时干预