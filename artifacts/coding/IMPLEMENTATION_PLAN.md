```markdown
# 铁魂 · Iron Equilibrium 实现计划 v0.1  
（供程序/美术/关卡评审，可直接落盘）

---

## 1. 目录结构（Perforce 单仓库 //depot/IronEq）
```
/IronEq
 ├─/Assets
 │  ├─/Art
 │  │  ├─/Characters        # 铠甲、武器、部位破坏模型
 │  │  ├─/Environments       # 五区域场景组件、熔岩/齿轮/黑水材质
 │  │  ├─/FX                 # 火星、铁水BAV槽、处决特效
 │  │  └─/Shaders            # RustAccumulate、ImpactGlow、WeightPenalty
 │  ├─/Audio
 │  │  ├─/Weapons            # 冲击等级1-5对应金属声
 │  │  └─/Voices             # 失衡惨叫、处决台词
 │  └─/Game
 │     ├─/Core               # 引擎无关纯逻辑，可单元测试
 │     ├─/Modules            # 业务模块，见第2节
 │     ├─/Networking         # 轻量联机，P2P+回滚
 │     ├─/UI                 # UMG/ImGui双方案，主机用UMG
 │     └─/Utils              # 配置表、日志、崩溃上报
 ├─/Config                   # Excel→json→bin 流水线
 ├─/Docs                     # 自动生成的API+策划注释
 ├─/Tools                    # 可视化BAV调参、关卡灰盒插件
 ├─/Build                    # TeamCity脚本，PC/XB/PS三端
 └─/Tests                    # 单元+集成+压力， nightly 跑
```

---

## 2. 模块划分（C++17 + UE5.3）

| 模块 | 职责 | 对外暴露 | 备注 |
|------|------|----------|------|
| BalanceCore | BAV公式、状态机、脆弱debuff | IBalanceInterface | 引擎无关，可gtest |
| ImpactCore  | IL vs STB判定、反弹BAV | IImpactInterface | 同上 |
| Equipment   | 部位重量、局部破坏、维修 | UEquipmentComponent | 绑定到Character |
| PlayerState | 死亡掉落、碎片数量、配装方案 | AIronPlayerState | 继承AGameStateBase |
| Campfire    | 存档、重配、修复、配装存储 | ACampfireActor | 调用PlayerState |
| NetSync     | 帧同步、延迟补偿、入侵buff | UIronNetDriver | 继承UE5 PushModel |
| AI          | Boss行为树、部位破坏感知 | UIronAIComponent | 与ImpactCore交互 |
| FX          | 火星、铁水裂纹、锈蚀度 | UIronFXLibrary | 材质参数暴露给美术 |

---

## 3. 关键接口（头文件即文档）

```cpp
// BalanceCore/Public/IBalanceInterface.h
class IRONCORE_API IBalanceInterface {
public:
    virtual float GetWeight() const = 0;
    virtual float GetBAV() const = 0;
    virtual void  ModifyBAV(float Delta, UObject* Instigator) = 0;
    virtual void  OnBreakBalance(UObject* Instigator) = 0;   // 进入失衡
};

// ImpactCore/Public/IImpactInterface.h
struct FImpactResult {
    bool bDeflected;   // 成功拆招
    float AttackerBAVDelta;
    float DefenderBAVDelta;
};
class IRONCORE_API IImpactInterface {
    virtual FImpactResult EvaluateImpact(int32 AttackerIL, int32 DefenderSTB) const = 0;
};
```

---

## 4. 实现顺序（与里程碑对齐）

| 周 | 任务 | 可测试点 | 交付形式 |
|----|------|----------|----------|
| W1 | BalanceCore单元测试通过 | gtest 100%覆盖 | Jenkins绿灯 |
| W2 | ImpactCore + 1把武器IL配置 | 控制台命令`keystone.ImpactTest` | 日志输出 |
| W3 | EquipmentComponent + 局部破坏原型 | 打腿20次→防御-50% | 关卡内打印 |
| W4 | 铸铁堡垒灰盒 + 熔炉骑士AI白模 | 通关时间≤3min | QA记录 |
| W5 | Campfire重配面板 + 配装存储 | 3套方案切换≤1s | UI录屏 |
| W6 | 联机8人局域网同步 | 延迟<100ms，0丢包 | TeamCity报告 |

---

## 5. 可测试点（自动化+人工）

| 标签 | 测试内容 | 工具 | 通过标准 |
|------|----------|------|----------|
| UNIT_BAV | 公式边界：重量=阈值1-1kg & +1kg | gtest | 误差<0.01 |
| UNIT_IMPACT | IL=5 vs STB=5 & STB=4 | gtest | bDeflected=true/false |
| INTEGRATION | 超重→木板塌陷 | 关卡脚本 | 触发率100% |
| UX_DEATH | 死亡掉落碎片→回收率 | PlaytestCloud | 24h回收≥30% |
| PERF | 1000火星粒子@1440p | Unreal Insights | ≥50fps |
| NET | 入侵者-30%重量同步 | 2xPC+1xXB局域网 | 数值一致 |

---

## 6. 风险前置代码

```cpp
// BalanceCore/Private/BalanceDebugger.h
#if ENABLE_BAV_DEBUG
CVarFloat(TEXT("keystone.BAV_Threshold1"), 20.0f);
CVarFloat(TEXT("keystone.BAV_Penalty"), 0.8f);
#endif
// 策划在UE控制台可实时调，无需重启
```

---

> 下一评审点：W2结束，BalanceCore & ImpactCore 单元测试报告+日志。  
```
