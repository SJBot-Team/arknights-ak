# -*- coding: utf-8 -*-
"""append_windup_table.py — ★前摇改为按职业/模板表驱动（用户补充）+ 无回归验证。"""
import io
import os
import shutil
import sys

sys.stdout.reconfigure(encoding='utf-8')

DOC = r'C:\Users\23922\Documents\ds_harness\ak\knowledge\04_数据对应与核验\54_1-1标定对局_复刻报告.md'
REG = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
DST = r'E:\__file\ak_kb\kb'

EXTRA = '''

---

## 二十九、★前摇改为"按职业/模板"表驱动（依用户补充）

### 29.1 用户补充（2026-09-15）
> 「不同敌人和不同干员的前摇均可能不同，这可能与**职业模板**有关，
>   也可能与**技能期间的攻击模组**有关，**敌人也是**。」

**⇒ 此前"统一比例（干员 0.55 / 敌人 0.10）"只是粗糙近似**，应改为**按模板分组**。

### 29.2 实现（`ak_sim/engine.py`）

**① 模块级比例表**（新增）：
```python
WINDUP_RATIO_BY_PROFESSION = {
    'PIONEER': 0.55,   # 先锋（芬，1-1 标定反推）
    'WARRIOR': 0.55,   # 近卫（月见夜，同场未单独标定 ⇒ 暂用同值）
    'SNIPER': 0.50, 'CASTER': 0.50, 'MEDIC': 0.50, 'SUPPORT': 0.50,   # 待校准
    'TANK': 0.55, 'SPECIAL': 0.55,
}
WINDUP_RATIO_DEFAULT_ALLY  = 0.55
WINDUP_RATIO_DEFAULT_ENEMY = 0.10
```

**② `_windup_frames` 改为表驱动**（优先级从高到低）：
1. `u._windup_ratio`（**单点覆盖**，便于按标定逐单位校准）；
2. `WINDUP_RATIO_BY_PROFESSION[u.profession]`；
3. `WINDUP_RATIO_DEFAULT_ALLY / _ENEMY`。

**③ 为"技能期间攻击模组"预留**：注释中说明——若技能 blackboard 含攻击模组字段
（如 `attack@atk_scale`）且技能激活，可据此覆盖 `u._windup_ratio`；**该分支待素材校准**。

### 29.3 本轮的两次实现修正（供反重复清单）
1. **表被插入 `@dataclass` 与 `class` 之间** ⇒ 破坏装饰器 ⇒ **SyntaxError**
   ⇒ 教训：**模块级常量应插到"首个 class/@dataclass 之前"**；
2. **`_windup_frames` 被定义了两次**（替换时未删旧定义）⇒ **旧定义覆盖新定义**，
   表面症状却是 `TypeError: takes 1 positional argument but 2 were given`（缺 `@staticmethod`）
   ⇒ 教训：**替换方法体后应 `grep` 确认无重复定义**。

### 29.4 验证：无回归
复测（表驱动 + 弹道）：**平均 \\|偏差\\| = 11.44 帧、\\|偏差\\|≤6 帧 10 条、最大 47**
—— 与"弹道实现后"的结果完全一致 ⇒ **表驱动改造功能等价（无回归）**。

### 29.5 说明与下一步
- **当前样本只有 1-1（芬＝先锋、月见夜＝近卫）** ⇒ **无法据此校准其它职业**，
  表中其余职业为占位值；**需更多标定素材**（不同职业干员、不同敌人）逐项校准；
- **下一步**：
  1. 用标定素材**逐职业/逐敌人**校准前摇比例（并记录样本量与来源）；
  2. 检查**技能期间的攻击模组**是否改变前摇（如技能替换普攻动作）；
  3. 把"**前摇比例表**"与"**弹道参数**"一并写入「信息查找链条」的**单位层**，
     作为"跑模拟前必须辨明的单位关联机制"的一部分（呼应前提 1）。
'''

s = io.open(DOC, encoding='utf-8').read()
if '二十九、★前摇改为' not in s:
    io.open(DOC, 'a', encoding='utf-8').write(EXTRA)
    print('已更新复刻报告')

ADD = (' **★前摇改为"按职业/模板"表驱动（依用户补充）+ 无回归验证（2026-09-15）**：'
       '①**用户补充**：「不同敌人和不同干员的前摇均可能不同，这可能与**职业模板**有关，'
       '也可能与**技能期间的攻击模组**有关，**敌人也是**」⇒ 此前"统一比例（干员 0.55/敌人 0.10）"'
       '只是粗糙近似，应改按模板分组；'
       '②**实现**：**(a) 模块级新增 `WINDUP_RATIO_BY_PROFESSION`**（PIONEER/WARRIOR=0.55 已知，'
       '其余职业为待校准占位）与 `WINDUP_RATIO_DEFAULT_ALLY=0.55`、`_ENEMY=0.10`；'
       '**(b) `_windup_frames` 改为表驱动**，优先级：`u._windup_ratio`（单点覆盖，便于逐单位标定）'
       '> `WINDUP_RATIO_BY_PROFESSION[u.profession]` > 阵营默认；'
       '**(c) 为"技能期间攻击模组"预留覆盖分支**（若技能 blackboard 含攻击模组字段且技能激活）；'
       '③**本轮两次实现修正（已记入反重复清单）**：**(a) 表被插入 `@dataclass` 与 `class` 之间**'
       '⇒ 破坏装饰器导致 SyntaxError ⇒ 教训"**模块级常量应插到首个 class/@dataclass 之前**"；'
       '**(b) `_windup_frames` 被定义两次**（替换时未删旧定义）⇒ 旧定义覆盖新定义，'
       '表面症状却是 `TypeError: takes 1 positional argument but 2 were given`（缺 @staticmethod）'
       '⇒ 教训"**替换方法体后应 grep 确认无重复定义**"；'
       '④**验证无回归**：表驱动 + 弹道复测 = **平均|偏差| 11.44 帧、≤6 帧 10 条、最大 47**，'
       '与弹道实现后**完全一致** ⇒ **改造功能等价**；'
       '⑤**说明与下一步**：当前样本仅 1-1（先锋+近卫）⇒ **无法校准其它职业**，表中其余职业为占位；'
       '**需更多标定素材**逐职业/逐敌人校准（并记录样本量与来源）；'
       '检查**技能期间攻击模组**是否改变前摇；把"**前摇比例表**"与"**弹道参数**"写入'
       '「信息查找链条」**单位层**，作为"跑模拟前必须辨明的单位关联机制"的一部分（呼应前提 1）；'
       '⑥**新增 `sim/draft/add_windup_table.py`、`fix_windup_table_pos.py`**；'
       '⑦**合规**：仅本地模拟计算与用户提供的数据；未触碰游戏文件/内存。 | 2026-09-15 |')

r = io.open(REG, encoding='utf-8').read()
ra = '\n\n## 冲突记录'
r = r.replace(ra, ADD + ra, 1)
io.open(REG, 'w', encoding='utf-8', newline='').write(r)
print('台账已记录')
for src, sub in ((DOC, r'knowledge\04_数据对应与核验'),
                 (r'C:\Users\23922\Documents\ds_harness\ak\sim\draft\add_windup_table.py', r'sim\draft'),
                 (r'C:\Users\23922\Documents\ds_harness\ak\sim\draft\ak_sim\engine.py',
                  r'sim\draft\ak_sim')):
    d = os.path.join(DST, sub, os.path.basename(src))
    os.makedirs(os.path.dirname(d), exist_ok=True)
    shutil.copy2(src, d)
shutil.copy2(REG, os.path.join(DST, 'management', 'tasks_registry.md'))
print('同步完成')
