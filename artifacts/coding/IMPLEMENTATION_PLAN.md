```markdown
# 《Neon Runner》实现计划

> 基于 Unity6 | 2D URP | 单仓库 | 6周交付

---

## 1. 目录结构（Assets/）

```
├─_Root
│  ├─Scenes
│  │  ├─Boot.unity
│  │  ├─Menu.unity
│  │  └─Game.unity
│  ├─Scripts
│  │  ├─Runtime
│  │  │  ├─Core
│  │  │  │  ├─Sight
│  │  │  │  ├─Noise
│  │  │  │  ├─Cargo
│  │  │  │  ├─Alarm
│  │  │  │  ├─Melee
│  │  │  │  └─GhostPath
│  │  │  ├─Level
│  │  │  │  ├─SO
│  │  │  │  ├─Grid
│  │  │  │  └─Score
│  │  │  ├─UI
│  │  │  ├─Save
│  │  │  ├─Localization
│  │  │  └─Chip
│  │  └─Editor
│  │      ├─LevelIO
│  │      └─ChipSOEditor
│  ├─ScriptableObjects
│  │  ├─Levels
│  │  └─Chips
│  ├─Prefabs
│  │  ├─Player
│  │  ├─Enemy
│  │  ├─Props
│  │  └─VFX
│  ├─Tiles
│  ├─Sprites
│  ├─Shaders
│  ├─Audio
│  └─Localization
```

---

## 2. 模块划分 & 关键接口

| 模块 | 主类 | 对外接口 | 事件 |
|---|---|---|---|
| Sight | `SightSystem` | `bool CanSee(Transform target)` | `OnSpot` |
| Noise | `NoiseManager` | `void Emit(Vector3 pos, float radius, EType type)` | `OnHeard` |
| Cargo | `CargoController` | `bool HasCargo; float SpeedMul` | `OnPick; OnDrop` |
| Alarm | `AlarmManager` | `void Trigger()` | `OnAlarmStart; OnAlarmEnd` |
| Melee | `MeleeStrike` | `void Strike(Vector2 dir)` | `OnKill; OnKO` |
| GhostPath | `GhostPath` | `void SetMarkers(List<Vector3> pts)` | — |
| Score | `LevelScore` | `int Stars` | `OnStarChange` |
| Chip | `ChipInventory` | `bool IsEquipped(ChipSO chip)` | `OnEquip` |
| Save | `SaveSystem` | `void SaveProfile(Profile p)` | — |

---

## 3. 实现顺序（周驱动）

### W1 原型
1. Boot→Menu→Game 场景框架  
2. TileGrid + 1白盒关卡  
3. PlayerMovement（8方向+翻滚）  
4. SightSystem 锥形射线  
5. MeleeStrike 1v1秒杀  
6. 撤离点触发→切场景→简易结算  

**可测试点**：FPS≥120；击杀后撤离计时≤3s

### W2 核心循环
1. CargoController 负重减速-25%  
2. NoiseManager 脚步声+波纹Shader  
3. AlarmManager 30s增援+封闭撤离  
4. GhostPath 3标记+路径预览  
5. LevelScore 3星条件+UI  
6. 3正式关卡数据SO  

**可测试点**：任意关卡3星通关；警报后30s内撤离失败

### W3 内容批量
1. Excel→SO导入器（EditorWindow）  
2. NodeGraph自动烘焙（A*）  
3. TilePalette+批量铺图  
4. 雨幕粒子+全屏后期开关  
5. 1章5关完整数据  

**可测试点**：1章平均帧≥100；关卡加载≤2s

### W4 芯片&输入
1. ChipSO + ChipInventory UI  
2. 存档/读档（JSON+AES）  
3. 本地化（CSV→ScriptableObject）  
4. Switch输入映射（Rewired或新InputSystem）  

**可测试点**：手柄无键位冲突；存档掉电不损坏

### W5 抛光
1. CRT死亡Shader+关电视音效  
2. 过场插画淡入淡出  
3. 音频混音（Snapshot）  
4. Steam成就接口  

**可测试点**：死亡→重开≤5s；成就即时弹出

### W6 送审
1. Switch平台编译+TCR自检  
2. 崩溃日志捕获（API→云）  
3. Demo分支锁定  

**可测试点**：0崩溃/0TCR违规

---

## 4. 关键配置示例

### LevelSO
```yaml
ID: 1-1
MapSize: {x:32, y:24}
Goal: AssassinateAndPickup
CargoWeight: Light
ReinforcePoints: 2
Special: None
ParTime: 90
StarReq:
  Spotted: 1
  Kills: 3
  Time: 90
```

### ChipSO
```yaml
Name: Air-Dash Mk2
DescKey: CHIP_AIR_DASH
Icon: chip_02
Cost: 120
Effect: DoubleAirDash
```

---

## 5. 自动化可测试点（PlayMode Test）

| 测试 | 断言 |
|---|---|
| Sight_BlockedByWall | `CanSee()==false` 当墙遮挡 |
| Cargo_DropSpeedRestore | 丢弃后SpeedMul==1 |
| Alarm_30sReinforce | Time.deltaTime累加30s时增援计数+1 |
| Score_3Star | 结算时Stars==3 |
| Save_RoundTrip | 存档前后Profile.Equals()==true |

---

## 6. 每日构建检查单

- [ ] 编译Win/Mac/Switch无Error  
- [ ] 运行Boot→Menu→Game无Exception  
- [ ] 随机关卡3星通关脚本通过  
- [ ] 帧率日志写入Artifacts  
- [ ] 版本号+分支名写入build_info.txt
```
