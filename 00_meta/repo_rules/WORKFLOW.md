# Git Workflow

## Goal

最基础、最常用的 Git 协作方式。  
目标是：分支清晰、提交易读、PR 易审、尽量少引入额外流程负担。

## Branching

- 日常开发基于 `dev` 分支进行。
- 每个独立任务新开一个分支，不直接在共享分支上堆叠大量未完成改动。
- 分支名使用英文短语，建议带类型前缀。

推荐格式：

```text
feature/<short-topic>
fix/<short-topic>
refactor/<short-topic>
docs/<short-topic>
test/<short-topic>
```

示例：

```text
feature/multi-project-workbench
fix/prompt-loading
docs/update-roadmap
```

## Commit

- 一个 commit 尽量只做一类事情。
- 提交前先确认代码能运行，或至少确认本次改动没有明显破坏主流程。
- 善用 AI 进行 review 和 debug。

提交标题使用英文，保持简短明确，详情说明可以用中文写。

推荐格式：

```text
type: short summary
```

常用 `type`：

- `feat`: 新功能
- `fix`: 缺陷修复
- `refactor`: 重构
- `docs`: 文档更新
- `test`: 测试调整
- `chore`: 杂项维护

示例：

```text
feat: add project-level reset flow
fix: restore project-scoped profile loading
docs: update prompt roadmap notes
```

如果需要补充说明，可以在 commit body 里用中文简要写：

- 改了什么
- 为什么改
- 有没有已知限制

## Pull Request

- 与 commit 同理。
- 提交 PR 前，至少自己过一遍 diff，确认没有误删、调试代码和无关变更。

推荐格式：

```text
type: short summary
```

示例：

```text
feat: improve structured prompt flow
fix: resolve workspace profile leakage
refactor: split frontend into static layers
```

PR 描述用中文，建议至少包含这几项：

- 背景：这次为什么要改
- 主要改动：核心改了哪些点
- 验证：跑了什么测试，或者手动验证了什么
- 风险：还有哪些没覆盖到

## Review

- Review 重点优先看行为变化、回归风险、状态流转、边界条件和测试覆盖。
- 如果只是文案、注释、样式微调，说明清楚即可，不必过度展开。
- 提 review 意见时，优先指出“会出问题的点”，其次再谈风格建议。

## Merge

- PR 合并前，确认目标分支是正确的。
- 合并前如果分支已经明显落后，先同步主线再处理冲突。
- 不要带着已知报错、已知脏调试输出直接合并。

## Minimal Rule

如果只记最简单的一版，就记下面 4 条：

1. 新任务开新分支。
2. commit 标题用英文，且一次只做一类改动。
3. PR 标题用英文，描述用中文写清背景、改动和验证。
4. 合并前自己先看一遍 diff，确认没有无关改动和调试代码。
