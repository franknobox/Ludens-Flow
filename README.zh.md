<p align="center">
  <img src="11_docs/IMAGE/LF.svg" alt="Ludens-Flow logo" width="96" />
</p>

<p align="center">
  <strong>结构化游戏开发的多 Agent 工作台。</strong>
</p>

<p align="center">
  <a href="README.md">English</a> ·
  <strong>简体中文</strong>
</p>

<p align="center">
  <a href="https://github.com/franknobox/Ludens-Flow">GitHub</a> ·
  <a href="agent_workbench/README.md">Workbench 文档</a> ·
  <a href="LICENSE">MIT License</a>
</p>

---

## Ludens-Flow 是什么？

Ludens-Flow 是一个面向游戏开发的 human-in-the-loop 多 Agent 工作台。它不是把大模型当成一个自由聊天助手，也不是把整个项目交给一个黑箱自动化流程，而是把 Agent 放回工程系统里：有项目边界、有工件、有工具权限、有状态流转，也有可以被看见和管理的工作过程。

它更关注：

- 如何澄清需求
- 如何推进策划与工程协作
- 如何让工件可追踪、可审阅、可复现
- 如何把文件、工具、工作区和前端工作台整合成一个可控系统
- 如何让用户在关键节点检查、修改、确认、导出或覆盖 Agent 的结果

## 目前已经具备的方向

- 多 Agent 工作流：设计、计划、工程、评审、辅导
- 工件驱动：`GDD`、`PROJECT_PLAN`、`IMPLEMENTATION_PLAN`、`REVIEW_REPORT`
- Web 工作台：项目切换、设置页、文件视图、对话、流式反馈、思考/进度流、工具过程展示、多主题支持
- MCP 引擎接入：通过受控能力层连接外部引擎；Unreal MCP 正在接入和验证，支持面向编辑器操作、Output Log、PIE 等方向继续扩展
- 文案能力：前端文案加工台支持外部参考、过程状态展示、Markdown / CSV 导出
- AIGC 快捷入口：整理图片、声音、视频、3D、UI、参考资料等游戏生产相关外部生成式服务入口
- 游戏 AI 配置中心：支持配置游戏内 AI 场景、模型服务、Prompt / Tool 组合、测试调用和导出包
- Level Layout Studio / 关卡设计台：本地离线接入关卡布局工具，保留导入导出能力，补充自动保存和工作台内交互修正
- 工作区与工具能力：项目级工作区、受控文件读写、目录创建、补丁与删除
- 模型路由：项目级 `model_routing` 图形化配置，支持按 Agent / 能力分配不同模型
- 多模态输入：图片、文本、代码文件、PDF
- 项目画像与 Skills：可在设置页维护 `USER_PROFILE.md`，并按项目启用外部导入的 Skills，后续支持自我沉淀复用流程

## 当前重点

近期主要推进：

- 稳定多 Agent 工作流核心、后端 API 拆分和端点覆盖
- 通过 MCP 连接真实游戏引擎，当前重点是 Unreal 编辑器侧操作、日志读取、PIE 和项目验证
- 打磨游戏 AI 配置中心，让用户能配置、测试、导出并理解实际接入游戏内 AI 的流程
- 将 AIGC 入口、文案导出、模型路由、关卡设计台等工具整理成连贯的项目工作流
- 强化项目级状态持久化、元数据安全、工作区隔离和浏览器侧恢复能力
- 优化工作台浏览体验、可观察性、设置管理、深浅色主题和响应式体验

## 它不是什么？

它不是“一个 prompt 直接生成完整游戏”的自动化系统。

它更像一个**结构化游戏开发工作台**，帮助开发者把思路、工件、实现和审阅组织起来。

## 快速开始

安装：

```bash
pip install -e ./agent_workbench
```

Web 态：

```powershell
.\agent_workbench\scripts\start_web.ps1
```

说明：`ludensflow` CLI 目前作为旧版/调试入口保留，暂不作为推荐启动方式。

## 重点文档

- [Workbench 使用说明](agent_workbench/README.md)
- [项目状态](STATUS.md)
- [Roadmap](11_docs/ROADMAP.md)

## 未来方向

后续会继续推进：

- 更深入的 MCP 引擎集成，包括 Unreal 编辑器操作、Output Log 读取、PIE 控制、视口/上下文捕获和项目侧验证
- Agent 驱动的模块自动化：用户描述目标后，Agent 可以在明确授权下调用文案、AIGC、MCP、模型配置、关卡设计等工作台模块
- 更实用的游戏内 AI 接入：配置 JSON、示例代码、使用指南、模型路由、流式输出、工具调用审计、缓存、频率限制、成本预算和降级策略
- 将关卡设计台逐步升级为一等本地关卡设计工作区，并探索 Agent 辅助生成布局、解释空间结构和回收结果
- 更强的多模态工作流，覆盖语音、图片、视频、UI 参考、世界模型探索和游戏素材生成
- 更顺滑的外部 AIGC 闭环：在 Ludens-Flow 内选择能力，跳转或调用外部服务，再把结果回收到项目工作流
- 更结构化的多 Agent 协作、角色化通信协议、可追踪决策和人工确认节点
- 收版验收基线、浏览器 smoke 测试和可重复的工作流评测

## 赞助支持

<p align="center">
  <img src="11_docs\IMAGE\mimo.png" alt="Xiaomi MiMO logo" width="360" />
</p>

Ludens-Flow 获得 **Xiaomi MiMO** 的 token 支持。

## 开源信息

- 仓库地址：<https://github.com/franknobox/Ludens-Flow>
- 开源协议：[MIT](LICENSE)

> 项目最初起步于 2026 SUAT AI Agent Innovation Competition，但当前定位是一个持续演进的开源项目。
