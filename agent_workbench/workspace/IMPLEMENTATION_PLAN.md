```markdown
# IMPLEMENTATION_PLAN.md

## 1. Unity 工程结构

遵循 Preset A（原型可读性优先），目录扁平化，Inspector 拖放友好。

```text
Assets/
├── _Scenes/                    # 所有场景，Build Settings 中按顺序添加
│   ├── 00_StartMenu.unity
│   ├── 01_Level_01.unity
│   └── 99_M0_Playground.unity  # 灰盒测试场景，保留至最终 Build
├── _Scripts/                   # 严格按游戏对象类型分文件夹，禁止跨文件夹引用
│   ├── Player/
│   │   ├── PlayerController.cs
│   │   ├── PlayerHealth.cs
│   │   └── PlayerInput.cs      # 封装 Input System 或旧 Input Manager
│   ├── Environment/
│   │   ├── Hazard.cs
│   │   ├── Collectible.cs
│   │   ├── MovingPlatform.cs
│   │   └── Checkpoint.cs
│   ├── Managers/
│   │   ├── GameManager.cs      # 单例，挂载于场景空物体
│   │   ├── UIManager.cs        # 管理 Canvas 各 Panel 显隐
│   │   ├── AudioManager.cs
│   │   └── SceneLoader.cs
│   └── Utils/
│       ├── Singleton.cs        # 泛型单例基类（可选，Game Jam 可直接写 static）
│       └── CameraFollow.cs
├── _Prefabs/                   # 运行时实例化对象，命名与脚本一致
│   ├── Player/
│   │   └── Player.prefab       # 包含 SpriteRenderer, Rigidbody2D, BoxCollider2D
│   ├── Environment/
│   │   ├── Platform_Static.prefab
│   │   ├── Platform_Moving.prefab
│   │   ├── Hazard_Spike.prefab
│   │   └── Pickup_Coin.prefab
│   ├── UI/
│   │   ├── HUD_Canvas.prefab
│   │   └── EventSystem.prefab
│   └── VFX/
│       └── JumpDust.prefab     # Particle System，对象池备用
├── _Art/
│   ├── Sprites/                # 导入设置：Filter Mode = Point（像素风）或 Bilinear
│   │   ├── Characters/
│   │   ├── Environment/
│   │   └── UI/
│   ├── Tilemaps/               # 若使用 Tilemap
│   │   ├── Palettes/
│   │   └── Tiles/
│   └── Animations/             # Animator Controller 与 Clips 同目录
│       └── Player/
├── _Audio/
│   ├── SFX/                    # 短音效，Load Type = Decompress on Load
│   └── Music/                  # 长音频，Load Type = Streaming
├── _Physics/                   # 物理材质
│   ├── PM_Player.physicsMaterial2D      # Friction = 0（防止斜坡卡住）
│   └── PM_Platform.physicsMaterial2D    # 默认即可
└── _Settings/                  # Unity 项目配置（Input Actions, URP Assets 等）
    └── InputSystem.inputsettings.asset
```

**目录规则**：
- 所有资源文件夹前缀 `_` 确保在 Project 窗口置顶。
- 脚本禁止引用 `UnityEditor` 命名空间，确保 Build 通过。
- Prefab 变体（Prefab Variant）仅在 M1 后使用，M0 阶段直接复制修改。

---

## 2. 系统级任务清单

### M0：灰盒原型（Day 1-3）

#### 2.1 玩家移动系统
**创建脚本**：`Assets/_Scripts/Player/PlayerController.cs`  
**挂载对象**：`Player` GameObject（Tag 设为 "Player"）  
**所需组件**：
- `SpriteRenderer`（Color 设为蓝色，Order in Layer = 10）
- `Rigidbody2D`（Body Type = Dynamic, Gravity Scale = 3, Collision Detection = Continuous, Interpolate = Interpolate）
- `BoxCollider2D`（Size 略小于 Sprite，Material 拖入 `PM_Player`）

**脚本实现要点**：
- 序列化字段：`[SerializeField] float moveSpeed = 8f; [SerializeField] float jumpForce = 16f; [SerializeField] LayerMask groundLayer;`
- 地面检测：使用 `Physics2D.Raycast(transform.position, Vector2.down, 0.6f, groundLayer)` 或 `Physics2D.BoxCast`，**禁止**使用 `CollisionStay2D`（不可靠）。
- 土狼时间（Coyote Time）：声明 `float coyoteTime = 0.1f; float coyoteTimeCounter;`，在离开地面时启动倒计时，期间允许跳跃。
- 输入缓冲（Input Buffering）：声明 `float jumpBufferTime = 0.1f;`，在 `Update` 中检测输入，在 `FixedUpdate` 中执行跳跃，提升手感。
- 移动逻辑：在 `FixedUpdate` 中使用 `rb.velocity = new Vector2(moveInput * moveSpeed, rb.velocity.y);`，**禁止**使用 `AddForce` 做基础移动（难以控制）。

#### 2.2 游戏管理器
**创建脚本**：`Assets/_Scripts/Managers/GameManager.cs`  
**挂载对象**：场景空物体命名为 `GameManager`（Tag 设为 "GameManager"）  
**实现模式**：
```csharp
public class GameManager : MonoBehaviour 
{
    public static GameManager Instance;
    [SerializeField] Transform currentCheckpoint;
    [SerializeField] int maxHealth = 3;
    int currentHealth;
    
    void Awake() 
    {
        if (Instance != null) Destroy(gameObject); 
        else Instance = this;
        // 注意：Game Jam 中不使用 DontDestroyOnLoad，每个场景独立放置，数据用静态字段存储
    }
    
    public void RespawnPlayer() 
    {
        currentHealth--;
        if (currentHealth <= 0) SceneManager.LoadScene(SceneManager.GetActiveScene().name);
        else GameObject.FindWithTag("Player").transform.position = currentCheckpoint.position;
    }
    
    public void SetCheckpoint(Transform cp) => currentCheckpoint = cp;
}
```

#### 2.3 危险区域与胜利区域
**创建脚本**：`Assets/_Scripts/Environment/Hazard.cs`  
**挂载对象**：红色 Cube（SpriteRenderer Color = #FF4444），Tag 设为 "Hazard"  
**Collider**：`BoxCollider2D`（Is Trigger = false）  
**脚本逻辑**：`OnCollisionEnter2D(Collision2D col) { if (col.gameObject.CompareTag("Player")) GameManager.Instance.RespawnPlayer(); }`

**创建脚本**：`Assets/_Scripts/Environment/WinZone.cs`  
**挂载对象**：绿色 Cube，Collider 勾选 Is Trigger  
**脚本逻辑**：`OnTriggerEnter2D(Collider2D other) { if (other.CompareTag("Player")) { Debug.Log("WIN"); UnityEditor.EditorApplication.isPlaying = false; /* 或加载下一关 */ } }`

#### 2.4 摄像机跟随
**创建脚本**：`Assets/_Scripts/Utils/CameraFollow.cs`  
**挂载对象**：Main Camera  
**实现**：`transform.position = Vector3.SmoothDamp(transform.position, target.position + offset, ref velocity, smoothTime);`，`offset` 设为 `(0, 0, -10)`。

---

### M1：完整关卡（Day 4-9）

#### 2.5 UI 系统
**创建脚本**：`Assets/_Scripts/Managers/UIManager.cs`  
**挂载对象**：`Canvas`（Render Mode = Screen Space - Overlay）  
**子对象结构**：
- `HUD`（Active）：含 Slider（生命值）、Text（金币数）
- `PausePanel`（Inactive）：含 "继续" 和 "返回主菜单" 按钮
- `WinPanel`（Inactive）：含 "再玩一次" 按钮

**脚本逻辑**：直接 `public void ShowWinPanel() { winPanel.SetActive(true); Time.timeScale = 0; }`，**禁止**使用 Scene 加载实现 UI 切换。

**按钮绑定**：Inspector 中 OnClick() 拖入对应 GameObject，选择 UIManager 方法。

#### 2.6 收集品与检查点
**创建脚本**：`Assets/_Scripts/Environment/Collectible.cs`  
**挂载对象**：金币 Prefab（CircleCollider2D Is Trigger = true）  
**脚本逻辑**：`OnTriggerEnter2D` 中 `GameManager.Instance.AddCoin(); Destroy(gameObject);`

**创建脚本**：`Assets/_Scripts/Environment/Checkpoint.cs`  
**挂载对象**：空物体 +  SpriteRenderer（旗帜图标），Collider Is Trigger = true  
**脚本逻辑**：`OnTriggerEnter2D` 中更新 `GameManager.Instance.SetCheckpoint(transform);`

#### 2.7 移动平台
**创建脚本**：`Assets/_Scripts/Environment/MovingPlatform.cs`  
**挂载对象**：平台 Prefab（Kinematic Rigidbody2D）  
**实现**：在 `FixedUpdate` 中 `rb.MovePosition(Vector2.MoveTowards(...))`，设置两个 Transform 点作为路径端点（Waypoint A/B）。
**关键细节**：玩家站立时需成为平台子物体，在 `OnCollisionEnter2D` 中 `col.transform.SetParent(transform)`，离开时 `SetParent(null)`。

#### 2.8 场景加载器
**创建脚本**：`Assets/_Scripts/Managers/SceneLoader.cs`  
**实现**：`public void LoadScene(string sceneName) { StartCoroutine(LoadAsync(sceneName)); }`，使用 `AsyncOperation` 配合简单黑屏 Image 淡入淡出（DOTween 或 LeanTween 可选，但建议直接用 `CanvasGroup.alpha` 插值，避免引入插件）。

---

### M2：打包与优化（Day 10-14）

#### 2.9 粒子特效
**创建 Prefab**：`JumpDust`（Particle System）
- Duration 0.5, Loop false, Start Lifetime 0.3
- Shape: Circle, Radius 0.1
- Emission: Burst 10 particles
- Renderer: Order in Layer = 5

在 `PlayerController` 中地面检测成功时 `Instantiate(jumpDustPrefab, transform.position, Quaternion.identity);`，**MVP 阶段不强制使用对象池**，但需确保粒子销毁 `Destroy(go, 1f)`。

#### 2.10 构建配置
**Player Settings**：
- Resolution: 1920x1080, Fullscreen = false（Windowed）
- WebGL: Compression Format = Disabled（避免浏览器兼容问题）
- macOS: Create Xcode Project = false（直接出 .app）

**Quality Settings**：V Sync Count = Every V Blank（锁 60fps，防止过热）。

---

## 3. 关键风险与替代方案

### 风险 1：Rigidbody2D 高速穿模与抖动
**症状**：玩家快速下落穿过薄平台，或在斜坡抖动。
**Plan A（首选）**：
- Rigidbody2D 设置 **Collision Detection = Continuous**。
- 地面检测使用 `Physics2D.BoxCast` 而非射线，检测范围 `Vector2(0.9f, 0.1f)`，确保边缘覆盖。
- 平台碰撞体使用 `BoxCollider2D` 且厚度至少 0.2 单位，**禁用 EdgeCollider2D**（易产生缝隙）。
**Plan B（降级）**：
若仍穿模，将玩家 Rigidbody2D 改为 **Kinematic**，完全通过代码控制移动（`rb.MovePosition`），自行实现重力与碰撞检测（参考 `CharacterController2D` 开源实现）。代价：失去物理互动，但彻底杜绝穿模。

### 风险 2：动画状态机复杂度失控
**症状**：Animator 中 Idle/Run/Jump 过渡条件冲突，角色卡住或动画不切换。
**Plan A（推荐）**：
- 仅保留 3 个状态：Idle, Run, Air（Jump 与 Fall 合并）。
- 所有过渡使用 `IsGrounded` Bool 参数，**禁用 Has Exit Time**，Transition Duration = 0（像素风）或 0.1（手绘风）。
- 代码直接控制：`animator.SetBool("IsGrounded", isGrounded); animator.SetFloat("Speed", Mathf.Abs(rb.velocity.x));`
**Plan B（终极简化）**：
彻底移除 Animator，在 `PlayerController` 中直接操作 `SpriteRenderer.sprite`：
```csharp
if (!isGrounded) sr.sprite = jumpSprite;
else if (Mathf.Abs(rb.velocity.x) > 0.1f) sr.sprite = runSprites[frameIndex];
else sr.sprite = idleSprite;
```
使用 `Time.time % animationSpeed` 控制帧率。代价：无动画混合，但节省 2 天调试时间。

### 风险 3：跨场景数据残留与单例爆炸
**症状**：使用 `DontDestroyOnLoad` 后，重复加载场景导致 GameManager 复制，或静态数据未重置。
**Plan A（Preset A 标准）**：
- **禁止 DontDestroyOnLoad**。每个 Scene 独立放置 `GameManager` 空物体，使用静态字段存储跨场景数据（如 `public static int GlobalCoinCount`）。
- 在 `StartMenu` 场景的 `GameManager.Awake()` 中重置所有静态字段：`GlobalCoinCount = 0;`。
**Plan B（应急）**：
若静态字段出现诡异数据残留，立即改用 `PlayerPrefs` 作为临时数据中转：
- 切换场景前：`PlayerPrefs.SetInt("Health", currentHealth);`
- 新场景 `Start()` 中读取：`currentHealth = PlayerPrefs.GetInt("Health", 3);`
代价：数据类型受限（仅 int/float/string），且需手动清理，但 100% 避免单例生命周期问题。
```
