# Ludens-Flow 文件写入与操作能力设计稿

## 1. 文档定位

这份文档用于定义 Ludens-Flow 后续文件写入与操作能力的整体方案。

目标不是做一个通用 IDE，也不是复制 Claude Code，而是为当前的游戏开发工作台补齐一套：

- 安全可控的文件操作能力
- 可见、可理解的执行过程反馈
- 可在设置页统一管理的权限边界

当前重点场景是：

- 在项目已批准的工作区内读取和修改文本文件
- 让 Agent 可以围绕游戏项目持续推进工作
- 让用户始终知道系统读了什么、改了什么、为什么能改

---

## 2. 设计原则

### 2.1 受控能力，而不是直接命令

文件操作必须是受控能力，不是让 Agent 获得“任意文件系统写权限”。

系统应始终显式约束：

- 操作发生在哪个项目
- 操作发生在哪个 workspace
- 操作的是哪种文件类型
- 当前是否允许写入
- 是否需要用户确认

### 2.2 路径边界必须统一判定

不要让每个工具各写一套路径检查逻辑。

统一的工作区路径审核层应负责：

- 相对路径解析
- workspace 清单检查
- 越界检查
- symlink / realpath 检查
- 写入权限检查
- 文件类型白名单检查

### 2.3 权限流程是系统事件，不是工具私有分支

权限确认、执行进度、改动结果应被当作系统级事件流处理，而不是工具函数内部的隐式逻辑。

这样前端才能稳定展示：

- 正在校验权限
- 已通过 / 被拒绝
- 正在修改文件
- 已修改哪些文件
- 最终成功还是失败

### 2.4 前端要展示“过程”与“改动”，不只显示最终回复

最终体验不能只是“Agent 回复了一段话”。

我们需要让用户看到：

- 本轮参考文件
- 本轮执行步骤
- 本轮修改文件
- 每一步的结果

### 2.5 设置页是权限边界的一等入口

文件读写权限不应藏在提示词、工具实现或隐式后端逻辑里。

设置页需要成为正式入口，用来管理：

- 哪些 workspace 存在
- 哪些 workspace 可写
- 项目是否允许 Agent 写入
- 是否需要逐次确认

---

## 3. 参考项目中最值得借鉴的思路

本方案重点借鉴 `src-ClaudeCode` 的不是某个写文件函数，而是整体分层方式。

### 3.1 路径与权限判定层

参考点：

- `src/utils/permissions/pathValidation.ts`

值得借鉴的是：

- 所有路径先统一处理
- 区分 `read / write / create`
- 处理绝对路径、`~`、glob、路径穿越、UNC、realpath、symlink
- 再结合 allow / deny / working dir / sandbox allowlist 做最终判定

对 Ludens-Flow 的直接启发：

- 不要让 `unity_write_text_file`、`generic_patch_file` 等各自判路径
- 必须建立统一工作区边界层

### 3.2 权限作为标准事件流

参考点：

- `src/cli/structuredIO.ts`

值得借鉴的是：

- 工具发起执行前，先进入标准权限判断流程
- 权限结果再决定是否继续执行
- 这个过程是统一事件，不是某个工具独有逻辑

对 Ludens-Flow 的直接启发：

- 文件写入前，系统应统一发出 `permission_required`
- 确认结果再转为 `permission_granted` / `permission_denied`

### 3.3 上下文文件集合

参考点：

- `src/commands/files/files.ts`

值得借鉴的是：

- 系统知道“哪些文件已进入当前上下文”
- 可以显式列出，而不是靠模型隐式记忆

对 Ludens-Flow 的直接启发：

- 后续要支持“本轮参考文件”和“本轮修改文件”
- 让用户感觉系统是在围绕项目工作，而不是随机读一个文件

### 3.4 权限模式是系统配置

参考点：

- `permissionMode`
- `permissions`
- `can_use_tool`

值得借鉴的是：

- 权限模式是系统的一等概念
- 不是工具作者自行决定的隐藏逻辑

对 Ludens-Flow 的直接启发：

- 不应只依赖 `workspace.writable`
- 还应有项目级总开关和确认模式

---

## 4. Ludens-Flow 的四层实现模型

### 第 1 层：工作区边界层

目录建议：

- `agent_workbench/src/ludens_flow/workspaces/`

核心职责：

- 验证 workspace 是否存在且启用
- 检查 workspace 是否允许当前操作
- 解析相对路径到真实目标
- 校验是否越界
- 处理 symlink / realpath 风险
- 检查文件类型是否允许

建议接口：

```python
resolve_workspace_target(project_id, workspace_id, relative_path, operation)
validate_workspace_path(project_id, workspace_id, relative_path, operation)
check_workspace_write_permission(project_id, workspace_id, relative_path, file_kind)
```

其中 `operation` 第一阶段只支持：

- `read`
- `write`
- `create`

第一阶段不做：

- `delete`
- `move`
- 任意目录重命名

### 第 2 层：文件操作工具层

目录建议：

- `agent_workbench/src/ludens_flow/tools/`

第一阶段工具建议：

- `workspace_read_files_batch`
- `workspace_write_text_file`
- `workspace_patch_text_file`

工具输入统一包含：

- `workspace_id`
- `path` 或 `paths`
- `content` / `patch`
- 可选 `reason`

第一阶段允许的文件类型白名单：

- `.cs`
- `.json`
- `.md`
- `.txt`
- `.yaml`
- `.yml`
- `.asmdef`
- `.uxml`
- `.uss`
- `.shader`

第一阶段明确禁止：

- `.unity`
- `.prefab`
- `.meta`
- 二进制资源文件

### 第 3 层：执行事件层

文件操作应统一发出以下事件：

- `tool_started`
- `permission_required`
- `permission_granted`
- `permission_denied`
- `tool_progress`
- `file_changed`
- `tool_completed`
- `tool_failed`

其中 `file_changed` 至少包含：

- `workspace_id`
- `workspace_label`
- `path`
- `change_type`: `created` / `modified`
- `summary`
- 可选 `diff_preview`

这一层是连接后端执行与前端展示的关键。

### 第 4 层：设置管理层

设置页需要正式承载这些概念：

#### 项目级总开关

- `允许 Agent 写入文件`

#### 项目级确认模式

建议第一阶段支持两档：

- `每次写入前确认`
- `允许安全写入自动执行`

#### 工作区级权限

每个 workspace 继续保留：

- `enabled`
- `writable`

后续可扩展：

- `allowed_file_types`

---

## 5. 第一阶段接口与事件建议

### 5.1 后端工具接口

#### `workspace_read_files_batch`

用途：

- 一次读取多个文件
- 降低 Agent 来回单文件调用次数

输入：

```json
{
  "workspace_id": "unity-main",
  "paths": ["Assets/Scripts/A.cs", "Assets/Scripts/B.cs"]
}
```

#### `workspace_write_text_file`

用途：

- 创建或覆盖写入一个文本文件

输入：

```json
{
  "workspace_id": "unity-main",
  "path": "Assets/Scripts/NewFile.cs",
  "content": "...",
  "reason": "Create initial gameplay script"
}
```

#### `workspace_patch_text_file`

用途：

- 以受控 patch 方式修改现有文本文件

输入：

```json
{
  "workspace_id": "unity-main",
  "path": "Assets/Scripts/StoryManager.cs",
  "patch": "...",
  "reason": "Adjust dialogue progression logic"
}
```

### 5.2 SSE / 前端事件

第一阶段前端至少消费这些事件：

- `permission_required`
- `permission_granted`
- `permission_denied`
- `tool_started`
- `tool_progress`
- `file_changed`
- `tool_completed`
- `tool_failed`

---

## 6. 前端展示建议

### 6.1 对话区过程卡片

在现有聊天区中，增加执行过程卡片，显示：

- 当前步骤
- 当前状态
- 对应文件或工作区

示例：

- 正在校验工作区权限
- 正在读取 2 个脚本文件
- 正在写入 `Assets/Scripts/StoryManager.cs`
- 已完成

### 6.2 文件改动卡片

在 `file_changed` 事件出现时，显示：

- 工作区标签
- 文件路径
- 创建 / 修改
- 一行摘要

### 6.3 本轮文件上下文

后续建议在 assistant 回复下方增加轻量信息：

- `本轮参考文件`
- `本轮修改文件`

这会强化“系统在围绕工程工作”的感觉。

---

## 7. Settings 页面建议

第一阶段 Settings 中与文件写入相关的配置建议包括：

### 7.1 工作区清单

现有能力继续保留：

- 创建 workspace
- 启用 / 停用
- 标记是否可写

### 7.2 写入权限

新增项目级权限区：

- `允许 Agent 写入文件`
- `需要用户确认后执行写入`

### 7.3 说明文案

应明确说明：

- Agent 只能在批准的 workspace 中操作
- 只有可写 workspace 才允许写入
- 被禁止的文件类型不会被修改

---

## 8. 第一阶段验收标准

第一阶段完成的标志：

- 用户可以在 Settings 中将某个 workspace 标记为可写
- Agent 可以安全写入一个白名单文本文件
- 越界路径会被统一拒绝
- 前端可以清楚显示：
  - 正在校验权限
  - 正在执行工具
  - 已改动哪些文件
  - 成功还是失败
- 项目设置里可以控制：
  - 是否允许写入
  - 是否需要确认

---

## 9. 实施顺序建议

建议按这个顺序推进：

1. 建立工作区边界层
2. 先做 `workspace_read_files_batch`
3. 再做 `workspace_write_text_file`
4. 接通执行事件流
5. 前端展示过程卡片与文件改动卡片
6. Settings 补项目级写入权限管理
7. 最后再做 `workspace_patch_text_file`

第一阶段不建议立即做删除能力。

---

## 10. 一句话总结

Ludens-Flow 后续的文件操作能力，不应是“Agent 直接改文件”，而应是：

**工作区边界层 + 文件工具层 + 执行事件层 + 设置权限层**

只有这样，文件写入才会既安全、可控，又具备产品级可解释性。
