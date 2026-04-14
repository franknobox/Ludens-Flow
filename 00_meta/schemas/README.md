# Schemas

## Goal

这里用于记录 Ludens-Flow 当前正在使用的文档层协议说明。

这批文档的定位是：
- 给开发者、协作者、后续维护者看的协议说明
- 对齐当前运行时代码里的真实 schema
- 作为 prompt、前端、graph、agent 之间的数据契约参考

这里的文档不是运行时代码真源。
运行时代码真源目前在：
- `agent_workbench/src/ludens_flow/schemas/`

## Current Schemas

- `discuss.md`
  - 对应 discuss 阶段共享输出协议
  - 当前字段为 `reply / state_updates / profile_updates / events`

- `review_gate.md`
  - 对应 Review 阶段的结构化门禁协议
  - 当前字段为 `status / targets / scores / issues`

## Notes

- 文档层 schema 应尽量描述“当前已经稳定存在的字段”，不要超前写未来字段。
- 如果运行时代码改了字段结构，这里的文档也要同步更新。
- 如果后续补更严格的校验规则，也应优先先更新这里的协议说明。
