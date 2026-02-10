# 《Neon Runner》项目计划

> Unity6 | 2D俯视角 | 赛博潜行 | 关卡制 | 4-6h一周目 | PC+Switch

---

## 里程碑（6周冲刺，每周=5人日）

| 周 | 目标 | 可玩验证 | 交付物 | 退出准则 |
|---|---|---|---|---|
| W1 原型 | 可行走+视野+击杀+撤离 | 1白盒关卡 | ①可执行Win/Mac②GDD冻结③Trello看板 | 无编译错误，FPS≥120 |
| W2 核心循环 | 负重+警报+评分+3星 | 3正式关卡 | ①关卡编辑器②3星UI③音效占位 | 任意关卡3星通关 |
| W3 内容批量 | 40关Excel→SO+美术批量导入 | 1章(5关)全通 | ①TilePalette②角色动画③雨幕后期 | 1章平均帧≥100 |
| W4 芯片&输入 | 芯片商店+本地化+手柄 | 全芯片解锁 | ①存档/读档②Switch开发机运行③中文/EN | 手柄无键位冲突 |
| W5 抛光 | CRT死亡+过场插画+音频混音 | 全关卡通关 | ①成就②SteamSDK③ESRB资料 | 无A级Bug |
| W6 送审 | Switch提审+Steam上线准备 | 正式Demo | ①商店页②Trailer③PRKey | 0崩溃/0TCR违规 |

---

## 任务拆分（Backlog ≈ 180人时）

### 程序（60h）
- `SightSystem.cs` 视野锥+射线（8h）
- `NoiseManager.cs` 声呐波纹（6h）
- `GhostPath.cs` 路径预测+标记（6h）
- `CargoController.cs` 负重减速+丢弃（5h）
- `MeleeStrike.cs` 近战+投掷（5h）
- `AlarmManager.cs` 增援+撤离点封闭（6h）
- `LevelScore.cs` 3星逻辑（4h）
- `ChipInventory.cs` ScriptableObject商店（6h）
- 存档/读档+本地化（8h）
- Switch输入+成就（6h）

### 关卡（40h）
- Excel→SO管线脚本（8h）
- 40关手动摆放+节点图烘焙（32h）

### 美术（40h）
- 角色4方向×8帧（16h）
- TileSet 128块（8h）
- 雨幕粒子+Shader Graph残影（8h）
- 过场插画8张（8h）

### 音频（20h）
- 脚步声/击杀/警报SFX（10h）
- 赛博Lo-Fi BGM 6首（10h）

### QA（20h）
- 自动化回归脚本（8h）
- 兼容性测试PC×3+Switch×1（12h）

---

## 角色分工（5人团队）

| 角色 | 姓名 | 主责 | 副责 | 日站会时段 |
|---|---|---|---|---|
| PM | Li | 里程碑、对外、Trello | Switch提审 | 10:00-10:15 |
| Tech Lead | Wang | 所有核心系统、CodeReview | 存档/成就 | 同上 |
| Level Designer | Zhang | 40关、节点图、Excel管线 | 教学关文案 | 同上 |
| Artist | Zhao | 角色+Tile+UI+Shader | Trailer分镜 | 同上 |
| QA/Sound | Chen | SFX+BGM+自动化测试 | SteamSDK集成 | 同上 |

---

## 风险与缓解

| 风险 | 概率 | 影响 | 缓解措施 | 触发阈值 |
|---|---|---|---|---|
| Unity6正式版Bug | 中 | 高 | ①锁定b18②每日构建③回滚方案 | 连续2天阻塞 |
| Switch帧率<60 | 低 | 高 | ①雨幕分级②后期开关③LOD贴图 | 实测<55fps |
| 40关制作超时 | 高 | 中 | ①先完成20关②变体=脚本旋转③外包2关 | 周燃尽<80% |
| 无版号导致Switch延期 | 中 | 高 | ①Steam先行②Demo软上线③资料预提交 | 提交前30天无回执 |
| 音频版权纠纷 | 低 | 中 | ①使用内部作曲②购买独占③备用曲库 | 授权链缺失 |

---

## 燃尽图（示意）

```
180h ┤                 *
     ┤             *
     ┤         *
     ┤     *
     ┤ *
     └───────────────
       W1 W2 W3 W4 W5 W6
```

---

## 工具链

- 版本：GitHub私有仓库+GitLFS（*.psd *.wav）
- CI：GitHub Actions→Unity6→IL2CPP Win/Mac/Switch
- 任务：Trello（列表=Backlog/W1/W2…/Done）
- 文档：Notion（GDD/QA报告/会议纪要）
- 每日构建：11:30自动上传Steam内部分支

---

> 冻结日期：本周五17:00后任何需求变更需PM+TechLead双签。
