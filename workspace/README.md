# Workspace 目录说明

`workspace/` 是 Ludens-Flow 的运行时工作区，属于临时/会话数据，不纳入版本控制。

当前补充说明：

- `workspace/` 现在主要作为工作台根目录使用
- 真正的项目运行数据默认落在 `workspace/projects/<project_id>/`
- 外部导入的 Skills 默认落在 `workspace/skills/installed/<skill_id>/`
- 首次启动时会自动创建第一个项目 `project-1`
- 如果旧版单项目文件还直接放在 `workspace/` 根目录，系统会在首次启动时自动迁移到 `workspace/projects/project-1/`
- `reset` 现在是"当前项目级"操作，不再是整个 `workspace/` 的全局重置

## 多项目工作区结构

当前推荐的工作区结构如下：

```text
workspace/
├── .active_project
├── skills/
│   └── installed/
│       └── <skill_id>/
│           ├── skill.json
│           └── prompt.md
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

主要内容（历史单项目结构的说明仍保留，便于理解运行时文件类型）：

- `state.json`：状态机当前运行状态（phase、迭代计数、对话上下文等）
- `logs/`：运行日志
- `trace.log`：节点进入/退出轨迹
- `router.log`：阶段路由决策记录
- `artifacts.log`：工件写入审计记录
- `images/`：图片输入的临时缓存（通常 reset 会清空）
- `memory/`：运行时快照、历史补丁、临时记忆
- `dev_notes/`：开发过程笔记（如 DEVLOG）
- `patches/`：补丁建议文件
- `USER_PROFILE.md`：当前项目的用户画像文件，可在设置页编辑
- `GDD.md` / `PROJECT_PLAN.md` / `IMPLEMENTATION_PLAN.md` / `REVIEW_REPORT.md`：
  工作流产出的工件文件

全局 Skills 结构：

- `skills/installed/<skill_id>/skill.json`：Skill 元数据
- `skills/installed/<skill_id>/prompt.md`：Skill 提示词或使用说明

Skills 是全局安装、项目级启用；启用关系保存在对应项目目录中。

## 项目元数据持久化

项目目录下的元数据（如 `mcp_connections`、`model_routing` 等）与运行时数据统一持久化在项目级，不会意外丢失：

- 元数据写入采用**原子写**（先写临时文件，再 `os.replace` 替换），避免写一半导致文件损坏。
- 如果某项目元数据损坏（如 JSON 解析失败），`list_projects()` 会将其隔离并标记 `metadata_error`，不会阻塞其他项目的正常加载。
- 删除操作（清空 `workspaces` 或 `mcp_connections`）后，通用的 `touch_project()` 不会把旧的 stale 快照重新写回，防止已删除的配置被意外"复活"。

说明：

- 启动 API/CLI 时会自动创建缺失目录和基础文件。
- 如果目录不存在，可直接运行项目自动生成，无需手动恢复。
- 在多项目模式下，上述文件通常位于 `workspace/projects/<project_id>/` 下，而不是直接位于 `workspace/` 根目录。
