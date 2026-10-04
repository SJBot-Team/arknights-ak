# 1cc3.bin：游戏脚本定义 AssetBundle（2026-09-02 调零提供）

> 来源：调零通过 QQ 发送（E:\QQ\1cc3.bin，384KB，2026-09-02 下载）。
> 用途（已实证）：**全游戏 MonoScript 类定义 bundle**——与干员/敌人 prefab 一起加载，
> 即可把 MonoBehaviour 解析为具体 C# 脚本类（解决此前"脚本类名跨 bundle 解析失败"问题）。

## 内容
- UnityFS（Unity 2021.3.39f1），5906 个 MonoScript，**5841 个 Torappu.\* 类**
- 战斗相关（Battle/Action 1325 个）：Torappu.Battle.\*（Character/UnitMode/SelectorTrigger/
  AdvancedCharacterValidator…）、Torappu.Battle.Abilities.\*（MeleeAttack/UberEffectEmitter/
  GlobalAuraAbility…）、Torappu.Battle.Projectiles.\*（SimpleProjectile/ScanMovement…）等

## 实证（贾维 prefab char_349_chiave）
联合加载 1cc3.bin + prefab，11 个 MonoBehaviour 脚本类名全部解析：
`Torappu.Battle.Character`（本体）/`Talent`（天赋）/`UnitMode`（形态）/
`Abilities.MeleeAttack`（近战攻击）/`Abilities.GlobalAuraAbility`（全局光环）/
`BlockedOrAdvancedSelector`（阻挡索敌选择器）/`ShadowController`（影子）…

## 用法（脚本参考）
```python
env = UnityPy.load("1cc3.bin"); env.load_file("char_xxx.ab")  # 同 env 加载
d = obj.read(); s = d.m_Script.read()
s.m_Namespace + "." + s.m_ClassName  # → Torappu.Battle.Character
```

## 意义
- 组件层 ↔ 代码层桥梁：prefab 挂载脚本 → 类名 → 配合 il2cpp/IDA 定位具体实现
- 未来可批量：全部干员/敌人 prefab + 1cc3 → "挂载脚本清单"（组件组成语义表）
