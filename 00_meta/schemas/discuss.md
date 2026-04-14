# Discuss Schema

## Goal

`Discuss Schema` 用于描述 discuss 阶段 Agent 的共享结构化输出协议。

当前适用范围：
- `DesignAgent` discuss
- `PMAgent` discuss
- `EngineeringAgent` plan_discuss

当前运行时代码对应：
- `agent_workbench/src/ludens_flow/schemas/discuss.py`

## Shape

标准结构如下：

```json
{
  "reply": "显示给用户的自然语言回答",
  "state_updates": {},
  "profile_updates": ["[PROFILE_UPDATE] key: value"],
  "events": []
}
```

## Fields

### `reply`

- 类型：`string`
- 用途：给用户看的主要自然语言回复
- 说明：
  - 这是用户侧最直接看到的正文
  - 可以有内部结构感，但在协议层仍然是单个字符串
  - 如果模型给出非字符串值，运行时会转成字符串

### `state_updates`

- 类型：`object`
- 用途：给系统状态的增量更新
- 说明：
  - 用于合并回 `LudensState`
  - 当前常见内容包括：
    - `style_preset`
    - `decisions`
    - `review_gate`
    - 其他阶段相关增量状态
  - 如果不是对象，运行时会归一为空对象

### `profile_updates`

- 类型：`array[string]`
- 用途：给 `USER_PROFILE.md` 的更新条目
- 说明：
  - 推荐内容格式仍然是 `[PROFILE_UPDATE] key: value`
  - 运行时会过滤 `None` 和空白项
  - 如果传入单值而不是数组，运行时会包装成单元素数组

### `events`

- 类型：`array[string]`
- 用途：给 graph / router / 后续逻辑消费的事件标记
- 说明：
  - 用于表达当前回复引发的流程信号
  - 运行时会过滤 `None` 和空白项
  - 如果传入单值而不是数组，运行时会包装成单元素数组

## Runtime Behavior

当前运行时对 discuss schema 的处理规则：

- 优先尝试从回复中提取结构化 JSON 对象
- 支持以下包裹形式：
  - 纯 JSON
  - ```json 代码块
  - `<<TAG>> ... <<END_TAG>>` 标签块
- JSON 提取器支持：
  - 嵌套对象
  - 字符串中的 `{` `}`
  - 转义引号

如果结构化解析失败：
- 当前不会自动 fallback 成 `DiscussPayload`
- 调用方会收到：
  - `payload = None`
  - `remaining = 原始文本`

## Design Intent

这套 schema 的目标不是让所有 Agent 说同样的话，而是：
- 共享同一套结构化外壳
- 让不同 Agent 在 `reply` 内部保留各自的角色化表达

也就是说：
- schema 统一
- reply 风格不统一

## Future Direction

后续可能扩展但当前尚未纳入正式协议的方向包括：
- `follow_up_questions`
- `recommended_option`
- `risks`
- `next_steps`

这些字段只有在运行时代码正式接入后，才应写入本协议。
