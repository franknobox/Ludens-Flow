# Ludens-Flow Benchmark 设计草案

## 目标

Benchmark 的目标不是替代自动化测试，也不是泛泛评估“大模型聪不聪明”。  
它用于衡量 Ludens-Flow 作为游戏开发工作台的真实能力表现：主流程是否跑得顺、工件是否可用、工具执行是否可靠、前端反馈是否清楚。

V3 前的 benchmark 应优先服务两个目的：

- **收版验收**：确认演示路径和核心工作流不会在关键场景中失效。
- **能力对比**：在 Prompt、模型、工具和前端状态流调整后，能比较系统表现是否变好。

---

## Test / Smoke / Benchmark 的边界

### Test：正确性保障

Test 关注“代码有没有按规则工作”。  
它应该快速、稳定、可重复，默认不依赖真实 LLM、不依赖外部服务、不依赖网络。

适合放在 `agent_workbench/tests/`：

### Smoke：启动与主链路冒烟

Smoke 关注“当前环境是否能跑起来”。  
它应比 test 更贴近真实启动，但仍然尽量短。

适合覆盖：
- Web 产品态是否可启动。
- Web 开发态 API / frontend 链路是否可访问。
- `ludensflow-api` 是否能正常启动。
- 关键 API 是否返回基础状态。
- CLI 目前仅作为旧版/调试入口保留，可做兼容性 smoke，不作为推荐使用路径。

### Benchmark：能力与质量表现

Benchmark 关注“这个产品能力现在好不好用”。  
它可以更慢，可以使用真实模型，可以包含质量评分、耗时、成功率和人工 review。

适合覆盖：
- 一个真实游戏需求能否跑完整工作流。
- Agent 生成的 GDD / 计划 / 工程建议是否可用。
- 工具调用是否自然、有效、少绕路。
- 多模态输入是否被正确理解并引用。
- 工程执行闭环是否能读文件、改文件、运行验证并继续修正。
- 不同模型配置下的成功率、耗时和输出质量差异。

---

## V3 前建议的 Benchmark 集合

### 1. Demo Flow Benchmark

用于保证视频演示和基础工作流稳定。

覆盖内容：

- 从一句游戏想法开始进入 Design 讨论。
- 完成 GDD 定稿，并自动进入 PM 阶段。
- 完成 PM 定稿，并自动进入 Engineering 阶段。
- 完成 Engineering 定稿，进入 Review / DEV_COACHING。
- 过程中不出现“发送任意消息即可继续”这类旧交互残留。

核心指标：

- `phase_accuracy`
- `completion_rate`
- `manual_intervention_count`
- `latency_ms`

### 2. Artifact Quality Benchmark

用于评估核心工件是否干净、完整、可读。

覆盖内容：

- `GDD.md`
- `PROJECT_PLAN.md`
- `IMPLEMENTATION_PLAN.md`
- `REVIEW_REPORT.md`

检查点：

- 工件存在且非空。
- 没有 Markdown 代码块套壳。
- 没有 `[PROFILE_UPDATE]`、`[STATE_UPDATE]`、`[EVENT]` 等内部标记污染。
- 内容结构符合该工件用途。
- 关键信息能从前一阶段自然传递到后一阶段。

核心指标：

- `artifact_validity`
- `artifact_pollution_count`
- `section_completeness_score`
- `manual_quality_score`

### 3. Tool Capability Benchmark

用于评估受控工具能力是否真实可用。

覆盖内容：

- 读取工作区文件。
- 创建目录。
- 写入文本文件。
- Patch 文件。
- 删除文件。
- 权限确认与安全自动执行模式。
- 工具过程事件与前端展示。

检查点：

- 所有路径必须在项目工作区清单内。
- 写入、删除、patch 必须符合权限设置。
- 工具失败时有明确错误结构。
- 前端能展示工具开始、权限、变更、完成或失败。

核心指标：

- `tool_success_rate`
- `permission_correctness`
- `boundary_violation_count`
- `tool_event_completeness`

### 4. Engineering Loop Benchmark

用于评估系统是否接近通用 coding agent 的工程执行能力。

覆盖内容：

- 给定一个小型示例工程和明确 bug。
- Agent 搜索相关文件。
- Agent 读取上下文。
- Agent 生成 patch。
- 系统展示 diff。
- 执行测试或构建命令。
- Agent 根据失败输出继续修正。

第一版可以先使用小型 Python / TypeScript 示例工程；Unity 示例工程可作为后续扩展。

核心指标：

- `task_completion_rate`
- `diff_minimality`
- `test_recovery_rate`
- `command_output_used`
- `unsafe_action_count`

### 5. GameDev Capability Benchmark

用于评估 Ludens-Flow 与普通 coding agent 的差异化能力。

覆盖内容：

- Unity 工程阅读：定位角色移动、UI、关卡配置相关文件。
- Unity 工程修改：在 `.cs` 文件内完成小型功能修改。
- Blender MCP：检查连接、工具发现和能力映射。
- 文案加工台：按用途、风格、字数和限制生成游戏文案。
- 多模态输入：结合图片、PDF、Markdown 或代码文件进行讨论。

核心指标：

- `context_relevance`
- `game_artifact_usefulness`
- `engine_tool_readiness`
- `copywriting_constraint_following`
- `multimodal_reference_accuracy`

---

## 指标定义

建议先使用少量明确指标，不要一开始做复杂评分系统。

| 指标 | 含义 |
|---|---|
| `completion_rate` | 场景是否完成 |
| `phase_accuracy` | 阶段流转是否正确 |
| `artifact_validity` | 工件是否存在、非空、格式干净 |
| `schema_parse_rate` | 结构化输出解析成功率 |
| `tool_success_rate` | 工具调用成功率 |
| `boundary_violation_count` | 路径越界或权限违规次数 |
| `latency_ms` | 关键步骤耗时 |
| `manual_intervention_count` | 人工介入次数 |
| `manual_quality_score` | 人工质量评分 |

人工评分建议保持简单，例如 1-5 分：

- 1：不可用
- 2：有明显缺失，需要大量人工重写
- 3：基本可用，但需要修改
- 4：可直接作为草稿使用
- 5：质量稳定，可进入正式项目流

---

## 建议目录结构

```text
agent_workbench/
├─ tests/
│  └─ ...                 # 快速、稳定、默认 mock 的正确性测试
├─ scripts/
│  └─ smoke_install.py    # 启动与安装冒烟
└─ benchmarks/
   ├─ README.md
   ├─ cases/
   │  ├─ demo_flow.yaml
   │  ├─ artifact_quality.yaml
   │  ├─ tool_capability.yaml
   │  ├─ engineering_loop.yaml
   │  └─ gamedev_capability.yaml
   ├─ fixtures/
   │  ├─ sample_python_project/
   │  ├─ sample_ts_project/
   │  └─ sample_unity_project/
   ├─ runner.py
   ├─ scoring.py
   └─ reports/
```

---

## Benchmark Case 示例

```yaml
id: demo_flow_basic
name: Demo Flow Basic
type: workflow
mode: real_llm

input:
  project_seed: empty
  user_prompt: "我要做一个俯视角校园塔防 game jam 小游戏。"

steps:
  - send_user_message
  - commit_gdd
  - commit_pm
  - commit_engineering
  - wait_review_result

assertions:
  - phase_in: ["POST_REVIEW_DECISION", "DEV_COACHING"]
  - artifact_exists: GDD
  - artifact_exists: PROJECT_PLAN
  - artifact_exists: IMPLEMENTATION_PLAN
  - artifact_not_contains: "[PROFILE_UPDATE]"
  - artifact_not_wrapped_in_code_fence: true
  - obsolete_transition_text_absent: true

metrics:
  - completion_rate
  - phase_accuracy
  - artifact_validity
  - latency_ms
```

---

## 执行策略

### 每次开发提交前

运行 test，不运行 benchmark。

建议：

```powershell
python -m unittest discover -s agent_workbench/tests
```

### 发版或演示前

运行 smoke 和核心 benchmark。

建议：

- Web 产品态启动检查。
- Web 开发态启动检查。
- Demo Flow Benchmark。
- Artifact Quality Benchmark。
- Tool Capability Benchmark。

### Prompt / 模型 / 工具大改后

运行相关 benchmark，对比改动前后的报告。

重点看：

- 输出质量是否变好。
- 工具调用是否更稳定。
- 耗时是否明显增加。
- 工件污染是否回归。
- 人工介入次数是否减少。

---

## V3 前落地顺序

1. **先做 mock benchmark runner**
   - 不依赖真实 LLM。
   - 用固定 Agent 输出和模拟工具事件验证 benchmark 框架。

2. **再做真实 LLM demo benchmark**
   - 只覆盖 1-2 条核心演示路径。
   - 允许人工评分。

3. **补 Artifact Quality Benchmark**
   - 优先自动化检查工件污染、缺失和格式问题。

4. **补 Tool Capability Benchmark**
   - 覆盖文件读写、patch、delete、权限和工具事件。

5. **最后扩展 GameDev Capability Benchmark**
   - Unity、Blender、文案、多模态逐步加入。

---

## 非目标

V3 前暂不追求：

- 建立复杂排行榜。
- 做跨模型大规模横评。
- 完整自动评价游戏设计质量。
- 用 benchmark 阻塞所有日常开发。
- 把 benchmark 混进普通 unit test。

Benchmark 应该是产品能力仪表盘，而不是慢速测试套件。
