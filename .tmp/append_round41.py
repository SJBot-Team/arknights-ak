# -*- coding: utf-8 -*-
"""append_round41.py — 第四十一轮：费用条 ROI 实测定位成功 + 封顶停住验证 + 待查项。"""
import io
import sys

sys.stdout.reconfigure(encoding='utf-8')

DOC = r'C:\Users\23922\Documents\ds_harness\ak\knowledge\04_数据对应与核验\41_模拟器与自动打图_首版实现.md'
REG = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'

DOC_SEC = '''
### 7.68 费用条 ROI 实测定位成功；并实测"费用封顶后条停住"

#### 采集链路的实证（先补上一条硬数据）
`enter_drill.py 12 2.0`（adb display 2 采集 + 0.85 置信度阈值）录到的 9 帧，费用读数：

```
11(0.945) 13(0.948) 14(0.966) 15(0.944) 17(0.965) 18(0.940) 20(0.962) 20(0.962) 20(0.962)
```

⇒ 高置信度（0.94~0.97）且**单调递增 11→20**，与关卡模型 `显示费用 = 初始费用(10) + t` 完全吻合，
**采集→识别链路在真机端到端可信**。

#### 费用条位置：用帧间差分定出来（`locate_bar_offline.py`）
对上述 9 帧两两做差分、统计每行能量，**唯一稳定出现的强变化带**是：

```
y = 805…817，峰值在 y = 810…816（diff 39 ~ 81）
```

其余所有行 < 35（y=700–799 是费用数字区，diff 2–33；y=868–894 是"剩余可放置角色"一带，diff 2–17）。
⇒ **费用条 ROI ≈ y∈[805,817]，横向 x∈[1700,1920]**（此前我把 ROI 猜在 y 800–820，
方向是对的；上一轮读"恒定 fill=1.0"的真因是**画面根本不是游戏**，不是 ROI 错——见 §7.58/§7.60/§7.66）。

#### 实测验证了用户方法一的**前提**
用该 ROI 算相位（`verify_bar_phase.py`）：

| 帧 | 费用 | 相位 | 填充 | 亮列范围 |
|---|---|---|---|---|
| f0000 | 11 | 20 | 145px | 1739–1844 |
| f0002 | 14 | 16 | 120px | 1739–1819 |
| f0004 | 17 | 11 | 83px | 1739–1782 |
| f0006 | **20** | **0** | **220px** | 1740–1919 |
| f0007 | 20 | 0 | 220px | 1812–1855 |
| f0008 | 20 | 0 | 220px | 1812–1855 |

⇒ ①费用 < 上限时相位在变、填充宽度随相位缩放（83→120→145→220px）；
②**费用顶到上限（20）后相位恒为 0、填充恒为满格 220px ⇒ 条彻底停住**。
这正是用户所说"费用快满时要消耗它让条保持跳动"的实证依据 —— **封顶后相位不可用**。

#### 本轮未完成（诚实记录的断点）
相位↔时间的**精度验证尚未成立**：把相邻帧的"推得逻辑帧 = Δ费用×30 + Δ相位"与
`timestamps.csv` 的墙钟间隔比对时，发现**时间戳与本次运行的采样间隔不符**
（csv 显示相邻帧间隔 ~42s，而本次运行设的是 2s/帧）——说明该 csv 与当前帧集**不是同一次运行**。
⇒ 下一轮先修：`enter_drill.py` 记时间戳时把 **t0、fps、span 一并写进 csv 表头**，
采样后立刻校验"帧数 × 间隔 ≈ span"，再重做精度比对（目标是 ±1 帧）。
'''

REG_ADD = (
    ' **第四十一轮（费用条 ROI 实测定位成功；封顶停住实证）**：'
    '①**采集链路实证**：`enter_drill`（adb display 2 + 0.85 置信度阈值）录到 9 帧，费用读数 '
    '11→13→14→15→17→18→20 全部高置信度（0.94~0.97）且**单调递增**，与 `显示费用 = 初始费用(10) + t` 完全吻合；'
    '②**费用条 ROI 用帧间差分定出来了**：9 帧两两差分的行能量里，**唯一稳定强变化带是 y=805…817（峰值 810…816，diff 39~81）**，'
    '其余行 <35 ⇒ **费用条 ROI ≈ y∈[805,817]、x∈[1700,1920]**；'
    '（此前读"恒定 fill=1.0"的真因是画面根本不是游戏，见 §7.58/§7.60/§7.66，不是 ROI 错）'
    '③**实测验证了用户方法一的前提**：费用<上限时相位在变、填充宽度随相位缩放（83→120→145→220px）；'
    '**费用顶到上限 20 后相位恒 0、填充恒为满格 220px ⇒ 条彻底停住**，正是"快满时要故意消耗让它保持跳动"的实证依据；'
    '④**未完成的断点**：相位↔时间的精度验证**尚未成立**——比对时发现 `timestamps.csv` 与本次帧集不同源'
    '（csv 相邻帧间隔 ~42s，而本次设的是 2s/帧）⇒ 下一轮先修时间戳记录（把 t0/fps/span 写进表头并自校验'
    '"帧数×间隔≈span"），再重做精度比对（目标 ±1 帧）；'
    '⑤新增：`apps/locate_bar_offline.py`（离线帧间差分定位）、`apps/verify_bar_phase.py`（相位↔费用一致性检查）、'
    '`apps/locate_bar_in_battle.py`（进战斗后立刻采样，用于条在动的窗口期）；'
    '⑥合规：仅 adb/窗口接口与普通注入，不碰游戏内存；仅演习，未消耗理智。 | 2026-09-14 |'
)

s = io.open(DOC, encoding='utf-8').read()
anchor = '### 7.67 本轮新增/修改文件'
if anchor not in s:
    raise SystemExit('doc anchor not found')
s = s.replace(anchor, DOC_SEC + '\n### 7.69 本轮新增/修改文件', 1)
io.open(DOC, 'w', encoding='utf-8', newline='').write(s)
print('文档已追加 §7.68')

r = io.open(REG, encoding='utf-8').read()
ra = '\n\n## 冲突记录'
if ra not in r:
    raise SystemExit('registry anchor not found')
r = r.replace(ra, REG_ADD + ra, 1)
io.open(REG, 'w', encoding='utf-8', newline='').write(r)
print('台账已追加第四十一轮')

dst = r'E:\__file\ak_kb\kb'
import shutil
for f in ('knowledge\\04_数据对应与核验\\41_模拟器与自动打图_首版实现.md',):
    shutil.copy2(io.open.__self__ and __import__('os').path.join(r'C:\Users\23922\Documents\ds_harness\ak', f),
                 __import__('os').path.join(dst, f))
shutil.copy2(r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md',
             __import__('os').path.join(dst, 'management', 'tasks_registry.md'))
for f in ('locate_bar_offline.py', 'verify_bar_phase.py', 'locate_bar_in_battle.py'):
    src = __import__('os').path.join(r'C:\Users\23922\Documents\ds_harness\ak\code\vision\apps', f)
    dstd = __import__('os').path.join(dst, 'code', 'vision', 'apps', f)
    shutil.copy2(src, dstd)
print('同步完成')
