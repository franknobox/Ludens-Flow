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

Ludens-Flow 是一个面向游戏开发的多 Agent 工作台。它不是把大模型当成一个自由聊天助手，而是把 Agent 放回工程系统里：有项目边界、有工件、有工具权限、有状态流转，也有可以被看见和管理的工作过程。

它更关注：

- 如何澄清需求
- 如何推进策划与工程协作
- 如何让工件可追踪、可审阅、可复现
- 如何把文件、工具、工作区和前端工作台整合成一个可控系统

## 目前已经具备的方向

- 多 Agent 工作流：设计、计划、工程、评审、辅导
- 工件驱动：`GDD`、`PROJECT_PLAN`、`IMPLEMENTATION_PLAN`、`REVIEW_REPORT`
- Web 工作台：项目切换、设置页、文件视图、对话、流式反馈、思考/进度流、工具过程展示、多主题支持
- MCP 引擎接入：通过受控能力层连接外部引擎；Blender 和 Unity 已实机验证，Godot / Unreal 适配层已预留
- 文案能力：前端文案加工台支持外部参考、过程状态展示、Markdown / CSV 导出
- 工作区与工具能力：项目级工作区、受控文件读写、目录创建、补丁与删除
- 模型路由：项目级 `model_routing` 图形化配置，支持按 Agent / 能力分配不同模型
- 多模态输入：图片、文本、代码文件、PDF
- 项目画像与 Skills：可在设置页维护 `USER_PROFILE.md`，并按项目启用外部导入的 Skills，后续支持自我沉淀复用流程

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

- 更深入的引擎集成（viewport 截图、材质编辑、Unity 编辑器工作流）
- 更完整的文件工具与执行反馈（批量操作、编辑器侧可视化）
- 更结构化的多 Agent 协作与角色化通信协议
- Skills、用户画像与项目上下文在 Agent 运行时中的进一步接入
- Godot / UE 等更多引擎兼容
- 游戏内模型能力接入
- GitHub 等协作平台可视化
- 外部 AIGC 服务统一入口
- 收版验收基线与自动化 smoke 测试

## 开源信息

- 仓库地址：<https://github.com/franknobox/Ludens-Flow>
- 开源协议：[MIT](LICENSE)

> 项目最初起步于 2026 SUAT AI Agent Innovation Competition，但当前定位是一个持续演进的开源项目。
