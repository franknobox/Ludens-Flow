# Review Gate Schema

## Goal

`Review Gate Schema` 用于描述 Review 阶段的结构化门禁协议。

当前适用范围：
- `ReviewAgent` commit

当前运行时代码对应：
- `agent_workbench/src/ludens_flow/schemas/review_gate.py`
- `agent_workbench/src/ludens_flow/agents/review_agent.py`

## Shape

标准结构如下：

```json
{
  "status": "PASS",
  "targets": ["ENG"],
  "scores": {
    "design": 8,
    "engineering": 7
  },
  "issues": [
    {
      "target": "ENG",
      "severity": "MAJOR",
      "summary": "问题摘要",
      "fix_hint": "修复建议"
    }
  ]
}
```

在运行时，ReviewGate 通常以标签块形式附在评审正文后：

```text
<<REVIEW_GATE_JSON>>
{ ... }
<<END_REVIEW_GATE_JSON>>
```

## Fields

### `status`

- 类型：`string`
- 允许值：
  - `PASS`
  - `REQUEST_CHANGES`
  - `BLOCK`
- 用途：表达当前评审裁决
- 说明：
  - 如果值不合法，运行时会归一为 `REQUEST_CHANGES`

### `targets`

- 类型：`array[string]`
- 允许值：
  - `GDD`
  - `PM`
  - `ENG`
- 用途：指出需要回流或修改的目标阶段
- 说明：
  - 非法目标会被丢弃
  - 会自动去重

### `scores`

- 类型：`object`
- 当前支持键：
  - `design`
  - `engineering`
- 值类型：`number`
- 用途：给设计和工程两个维度打分
- 说明：
  - 运行时会把分数夹在 `0-10` 范围内
  - 非数字值会被忽略

### `issues`

- 类型：`array[object]`
- 每项结构：
  - `target`: `GDD | PM | ENG`
  - `severity`: `string`
  - `summary`: `string`
  - `fix_hint`: `string`
- 用途：列出当前最关键的问题项
- 说明：
  - 缺少 `target / severity / summary` 的 issue 会被忽略
  - `fix_hint` 可为空

## Runtime Rules

当前运行时在基础解析后，还会应用额外规则：

### Rule 1: BLOCK 优先

如果任何 issue 的 `severity == "BLOCK"`：
- 最终 `status` 会被强制改为 `BLOCK`

### Rule 2: 低分强制打回

如果：
- `design < 6`
  或
- `engineering < 6`

则：
- 最终 `status` 会被强制改为 `REQUEST_CHANGES`
- 如果 `targets` 为空：
  - `design < 6` 时默认打回 `GDD`
  - `engineering < 6` 时默认打回 `ENG`

### Rule 3: 正常通过兜底

如果没有触发上面两条规则，且 `status` 不是：
- `BLOCK`
- `REQUEST_CHANGES`

则最终会归一为：
- `PASS`

## Parse Failure Behavior

如果 ReviewGate 结构化解析失败：
- `ReviewAgent` 当前仍会走兜底逻辑
- 兜底结果会返回：
  - `status = REQUEST_CHANGES`
  - `targets = ["ENG"]`
  - `scores = {"design": 0, "engineering": 0}`

这属于当前实现的保护性策略，不代表理想长期形态。

## Design Intent

ReviewGate 的存在不是为了生成一段“好看的 JSON”，而是为了：
- 把评审结论变成系统可消费的数据
- 让 router / graph 能基于评审结果继续流转
- 把“评审文本”和“裁决信号”明确分开

## Future Direction

后续可能继续增强的方向包括：
- 更严格的 issue `severity` 枚举
- 更明确的 target 回流规则
- 更 typed 的全链路消费方式
- 评审正文与 gate 的前端联动展示

这些内容只有在运行时代码正式接入后，才应升级为正式协议字段。
