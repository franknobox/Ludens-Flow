# Workspace 目录说明

`workspace/` 是 Ludens-Flow 的运行时工作区，属于临时/会话数据，不纳入版本控制。

主要内容：

- `state.json`：状态机当前运行状态（phase、迭代计数、对话上下文等）
- `logs/`：运行日志
- `trace.log`：节点进入/退出轨迹
- `router.log`：阶段路由决策记录
- `artifacts.log`：工件写入审计记录
- `images/`：图片输入的临时缓存（通常 reset 会清空）
- `memory/`：运行时快照、历史补丁、临时记忆
- `dev_notes/`：开发过程笔记（如 DEVLOG）
- `patches/`：补丁建议文件
- `GDD.md` / `PROJECT_PLAN.md` / `IMPLEMENTATION_PLAN.md` / `REVIEW_REPORT.md`：
  工作流产出的工件文件

说明：

- 启动 API/CLI 时会自动创建缺失目录和基础文件。
- 如果目录不存在，可直接运行项目自动生成，无需手动恢复。
