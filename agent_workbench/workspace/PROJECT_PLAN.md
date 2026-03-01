你好！我是 Pax。看完这份 GDD，我得说：**全是"[待定]"等于没有设计文档**。两周 Game Jam 等不起这些不确定性，但我先基于"最安全的 Game Jam 假设"（2D 平台跳跃/俯视角动作）给你搭一个可落地的骨架。不过咱们得先补上几个致命缺口，否则第 5 天你会发现自己不知道游戏该怎么结束。

这是给你的执行蓝图，假设我们走 **"2D 平台跳跃 + 简单收集/逃脱机制"**（这是单人两周最可控的 Scope）。如果你实际想做的是卡牌构筑或 3D 射击，请立即叫停，因为排期要推倒重来。

---

# PROJECT_PLAN.md

## 项目约束与假设
- **开发周期**：14 天（最后 2 天为打包缓冲）
- **人力**：1 人全职（策划+程序+美术占位符）
- **目标平台**：PC Standalone (Windows/macOS)
- **技术栈假设**：Unity 2022 LTS, 2D URP（或 Built-in，别纠结渲染管线，Day 1 就定死别改）
- **核心玩法假设（需确认）**：玩家控制角色在 2D 关卡中移动、跳跃，收集物品到达终点即胜利。单次循环 30-90 秒。

---

## Milestones & 验收标准

### M0：灰盒原型（Day 1-3）
**目标**：验证核心手感，确认"这个游戏好玩"或"需要换方向"。  
**验收标准（Play Mode 可测）**：
1. 打开 `M0_Playground.unity` 场景，按 Play 进入 Play Mode。
2. 使用键盘（A/D 或方向键）控制一个灰色方块左右移动，Space 跳跃（含土狼时间 Coyote Time 0.1s）。
3. 场景中有另一个红色方块作为"敌人"，触碰后玩家重置到起点。
4. 场景最右侧有一个绿色触发区域，玩家进入后 Console 打印 "WIN" 并自动停止 Play Mode。
5. 帧率稳定在 60fps（Stats 面板查看）。

**禁止事项**：此阶段禁止做任何 Sprite 动画、禁止做开始菜单、禁止做对象池，全部用 Cube 和 Color 解决。

### M1：一个可通关的关卡（Day 4-9）
**目标**：内容完整流程跑通，有胜利/失败判定。  
**验收标准（Play Mode 可测）**：
1. 从 `StartMenu.unity` 点击"开始游戏"按钮，异步加载（允许简单淡入淡出）进入 `Level_01.unity`。
2. 关卡包含至少 3 种机制：平地、需跳跃的沟、移动平台（或巡逻敌人）。
3. 玩家有 3 点生命值的 UI 显示（Slider 或简单数字），跌落深渊或碰到敌人扣血并重生在检查点（Checkpoint）。
4. 收集全部 3 个"金币"（或任意收集物）后，终点门打开，进入后弹出胜利界面，显示用时和"再玩一次"按钮。
5. 失败（生命归零）时弹出失败界面，可返回主菜单。
6. 使用临时美术素材（itch.io 免费包或 Procedural Sprite），不再使用 Cube。

### M2：Game Jam 提交版（Day 10-14）
**目标**：打磨手感，消除阻塞性 Bug，打包上传。  
**验收标准（Build 可测）**：
1. 打出 Windows 和 macOS 双版本 Build，在干净机器（未安装 Unity 的电脑）上测试可运行。
2. 跳跃手感经过调校：重力倍数、跳跃高度、空中控制灵敏度 feels right（找 2 个朋友盲测说"不卡手"）。
3. 添加基础音效（跳跃、收集、受伤、胜利）和一段循环 BGM（音量可调）。
4. 无已知崩溃 Bug，无导致玩家卡死的碰撞体缝隙。
5. 上传 itch.io，填写页面描述，设置浏览器可玩（WebGL，如果 Scope 允许；否则仅提供下载）。

---

## Task Breakdown（Unity 工程模块）

### M0 Tasks

**Scripts/**（代码层，先搭框架）
- [ ] `PlayerController.cs`：用 `Rigidbody2D` + 射线检测（Raycast）做地面检测，**别用 `CharacterController`**（2D 项目用 Rigidbody2D 更快）。实现 Move, Jump, 基础重力。
- [ ] `Hazard.cs`：挂在敌人上，带 `OnCollisionEnter2D`，触碰后调用 `GameManager.RestartAtCheckpoint()`。
- [ ] `GameManager.cs`：单例，管理当前生命数、检查点坐标、胜利状态。别用 `DontDestroyOnLoad`，就在每个 Scene 里放一个，用简单静态变量存跨场景数据（Game Jam 足够）。
- [ ] `WinZone.cs`：触发器，进入后调用 `GameManager.TriggerWin()`。

**Scenes/**（场景搭建）
- [ ] 创建 `M0_Playground.unity`。
- [ ] 用 Tilemap（或简单 Sprite）搭建 3 段不同高度的平台。
- [ ] 放置玩家起点（空物体标记）、检查点（空物体）、终点 WinZone。

**Prefabs/**（可复用对象）
- [ ] `Player.prefab`：包含 SpriteRenderer（先给 Color 不同即可）、Rigidbody2D、BoxCollider2D、PlayerController 脚本。
- [ ] `Hazard.prefab`：红色 Sprite，Collider。
- [ ] `Platform.prefab`：静态碰撞体。

**禁止**：此阶段不做对象池，不做动画状态机，不做 Sprite 图集。

---

### M1 Tasks

**Scripts/**（扩展系统）
- [ ] `UIManager.cs`：管理主菜单、游戏内 HUD（生命值 Slider、金币计数）、胜利/失败面板的显示/隐藏。用简单的 `gameObject.SetActive()` 控制，别用场景加载做 UI 切换。
- [ ] `Collectible.cs`：金币逻辑，被触碰后销毁自身并通知 GameManager。
- [ ] `Checkpoint.cs`：触发器，更新 GameManager 的检查点坐标。
- [ ] `CameraFollow.cs`：简单的平滑跟随（SmoothDamp），不用 Cinemachine（减少依赖和学习成本）。
- [ ] `SceneLoader.cs`：封装 `SceneManager.LoadSceneAsync`，配合简单 Loading 画面（黑色 Image 淡入淡出）。

**Art/**（占位符替换）
- [ ] 导入 itch.io 免费素材包（推荐 [Kenney Assets](https://kenney.nl/assets) 或类似）。
- [ ] 替换 Player、Platform、Hazard、Collectible 的 Sprite。
- [ ] 使用 **Pixel Perfect Camera**（如果做像素风）或普通 Camera（如果是手绘风），Day 4 就必须定死，中途别换。

**Prefabs/**（内容生产）
- [ ] 制作 3 种平台变体（静态、移动、易碎）。
- [ ] 制作巡逻敌人 Prefab（简单左右移动的 Hazard）。
- [ ] 制作金币 Prefab。

**Scenes/**（关卡设计）
- [ ] `Level_01.unity`：使用 Tilemap（或手动拼 Prefab）搭建一个 60-90 秒通关流程的关卡。注意难度曲线：开始简单，中间有挑战，最后冲刺。
- [ ] `StartMenu.unity`：简单背景 + 标题 + 开始按钮 + 退出按钮。

**Audio/**（基础音效）
- [ ] 从 freesound.org 找 4-5 个 WAV/MP3 音效（Jump, Collect, Hurt, Win）。
- [ ] 找一段循环 BGM（Loopable）。
- [ ] `AudioManager.cs`：简单的单例，用 `AudioSource.PlayOneShot()` 播放音效，一个 `AudioSource` 放 BGM。

---

### M2 Tasks

**Scripts/**（Polish）
- [ ] 添加屏幕震动（Camera Shake）：受伤时随机偏移 Camera.transform.position 0.1 秒。
- [ ] 添加粒子特效：跳跃落地尘埃、收集金币 sparkle（使用 Unity 默认 Particle System，别花时间调复杂参数）。
- [ ] 输入缓冲（Input Buffering）：在落地前 0.1 秒按跳跃键，落地后自动跳（提升手感）。

**Build & Test**
- [ ] File > Build Settings，添加所有场景，测试 Windows Build。
- [ ] 测试 macOS Build（注意代码签名问题，Game Jam 可以告诉玩家按住 Control 点打开）。
- [ ] 测试 WebGL Build（如果决定发布网页版，注意压缩格式和加载条）。
- [ ] 用 Unity Profiler 检查是否有内存泄漏（主要是别让对象池无限增长，但咱们不用对象池，所以检查是否有 DontDestroyOnLoad 对象重复生成）。

---

## Unity 目录结构建议

```text
Assets/
├── _Scenes/                    # 所有场景文件
│   ├── StartMenu.unity
│   ├── Level_01.unity
│   └── M0_Playground.unity     # 原型场景，可保留作测试
├── _Scripts/                   # 所有 C# 脚本
│   ├── Player/
│   │   ├── PlayerController.cs
│   │   └── PlayerHealth.cs
│   ├── Environment/
│   │   ├── Hazard.cs
│   │   ├── Collectible.cs
│   │   └── MovingPlatform.cs
│   ├── Managers/
│   │   ├── GameManager.cs      # 单例，游戏状态
│   │   ├── UIManager.cs
│   │   ├── AudioManager.cs
│   │   └── SceneLoader.cs
│   └── Utils/                  # 小工具，如简单的单例基类
│       └── Singleton.cs
├── _Prefabs/                   # 所有预制体
│   ├── Player/
│   ├── Environment/
│   ├── UI/
│   └── Effects/
├── _Art/                       # 所有美术资源（非代码生成）
│   ├── Sprites/
│   │   ├── Characters/
│   │   ├── Environment/
│   │   └── UI/
│   ├── Tilemaps/               # 如果使用 Tilemap
│   │   ├── Tiles/
│   │   └── Palettes/
│   └── Animations/             # Animator Controllers 和 Clips
│       ├── Player/
│       └── UI/
├── _Audio/                     # 音效和音乐
│   ├── SFX/
│   └── Music/
├── _Physics/                   # 物理材质（2D/3D）
│   └── NoFriction.physicsMaterial2D
└── Settings/                   # Unity 项目设置（URP 配置等，默认保留）
```

**命名规范**：
- 文件夹用 PascalCase 或 下划线前缀（`_Scripts`）确保排在前面。
- Prefab 和 Script 同名（如 `Player.prefab` 对应 `PlayerController.cs`）。
- 场景内物体命名清晰：`Player`（不是 `GameObject`）、`Ground_Section_01`、`Enemy_Patrol_A`。

---

## 风险与缓解

### 1. Scope 蔓延（最高优先级）
**风险**：你看着 GDD 里的"[待定]"，想着"不如加个二段跳/射击/剧情对话/多结局"，导致第 10 天核心循环还没跑通。  
**缓解**：
- **铁律**：M0 结束前（第 3 天晚上），如果核心移动手感不对，**立即换更简单的机制**（例如从平台跳跃改为纯解谜推箱子，或从动作改为点击互动）。
- **清单机制**：任何新功能（如"我想加个 Boss 战"）必须先回答："砍掉什么来换时间？" 如果砍不掉已有内容，就拒绝新功能。

### 2. 物理抖动与穿模（技术风险）
**风险**：`Rigidbody2D` 在高速移动时穿过薄碰撞体（Thin Platform），或卡在斜坡。  
**缓解**：
- 使用 **连续碰撞检测**（Continuous Collision Detection）在 Rigidbody2D 上（Game Jam 性能开销可接受）。
- 地面碰撞体用 **方盒**（BoxCollider2D）并确保边缘对齐，别用 EdgeCollider2D（容易产生缝隙）。
- 玩家掉落检测用 `transform.position.y < -10` 代码判断，别依赖碰撞体检测"深渊"。

### 3. 动画状态机复杂度
**风险**：Animator 中状态过多（Idle, Run, Jump, Fall, Attack...），导致过渡条件冲突，角色卡住不动。  
**缓解**：
- **M0-M1 阶段只用 3 个状态**：Idle, Run, Air（跳跃/下落同一状态）。
- 用代码直接控制 `animator.SetBool("IsGrounded", isGrounded)`，别用复杂的 Transition 条件混合树。
- 如果角色动画简单（如像素画），直接用代码切换 Sprite（`spriteRenderer.sprite = jumpSprite`），**彻底不用 Animator**，节省大量调试时间。

### 4. 打包与平台兼容性
**风险**：第 14 天发现 WebGL 打包失败，或 macOS 版本打不开。  
**缓解**：
- **Day 7 就打出第一个测试 Build**（M1 中期），验证打包流程。
- WebGL 注意：Player Settings > Publishing Settings > Compression Format 改为 **Disabled**（避免某些浏览器解压问题）。
- macOS 版本在 Day 12 测试，留出时间处理 Gatekeeper 警告（玩家端解决方案）。

---

## 立即行动项（今晚完成）

1. **填补 GDD 缺口**：在下方 Change Request 处回复我，确认核心玩法到底是什么（平台跳跃？俯视角射击？卡牌？）。
2. **下载 Unity**：如果你还没装，现在就装 2022.3 LTS 版本，创建 2D (URP) 模板项目。
3. **找临时素材**：花 30 分钟在 [Kenney.nl](https://kenney.nl/assets) 下载一个免费的 Platformer Pack，解压丢进项目，明天直接用。

**记住**：Game Jam 的金标准不是"功能多"，而是"我能玩完并觉得有意思"。先让球滚起来！
