# -*- coding: utf-8 -*-
"""append_deploy_success.py — ★重大突破：战斗内部署协议完整打通。"""
import io
import os
import shutil
import sys

sys.stdout.reconfigure(encoding='utf-8')

REG = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
DOC = r'C:\Users\23922\Documents\ds_harness\ak\knowledge\04_数据对应与核验\49_战斗内操作协议_部署.md'
DST = r'E:\__file\ak_kb\kb'

MD = '''# 战斗内操作协议：**部署**（2026-09-15 实测打通）

> 本文件是"关卡内操作"的第一份可用协议。合规：全程在**演习**中验证（零理智），仅图形界面级操控。

## 一、结论（已验证成功）

**部署 ＝ 两段 `motionevent` 拖拽序列**：

```
① 选中并拖到格子
   motionevent DOWN  <卡片中心>
   motionevent MOVE  <中间点…>（至少 2 个中间点）
   motionevent UP    <目标格子>
      ⇒ 进入「朝向选择」状态：出现白色菱形选择框 + 红色「点击取消」

② 定朝向（拖动菱形到目标方向的角）
   motionevent DOWN  <菱形中心>
   motionevent MOVE  <朝目标方向移动>
   motionevent UP    <目标方向的角>
      ⇒ 部署完成
```

**成功判据（三重，实测全部成立）**：
1. 干员出现在战场上；
2. **底部对应卡片消失**（12 张 → 11 张）；
3. **「剩余可放置角色」计数 −1**（8 → 7）。

## 二、关键坑（都踩过）

| 做法 | 结果 |
|---|---|
| `input tap` 点卡片 | ❌ 会被判成**长按**，弹出干员详情面板（但**证明点击被接受**、且地图出现绿色可部署高亮格） |
| `input tap` 点绿色高亮格 | ❌ 不部署 |
| `input swipe` 卡片→格子（600/1000ms） | ❌ 不部署 |
| `motionevent DOWN`+`UP`（快速单击） | ❌ 无反应（太短） |
| **`motionevent DOWN→MOVE→MOVE→MOVE→UP`** | ✅ **成功进入朝向选择** |
| **再对菱形做一次 `DOWN→MOVE→UP`** | ✅ **完成部署** |

⇒ **规律：AK 的部署识别的是"带中间点的拖拽序列"，不是 tap、也不是单段 swipe。**
（`input swipe` 在部分模拟器上只发首末两点，游戏不认；`motionevent` 可精确控制每个点。）

## 三、与 MAA 定义的对应

| MAA 任务 | 定义 | 对应本协议 |
|---|---|---|
| `BattleDeployWhenPause` | `{"algorithm":"JustReturn","specialParams":[1]}` | **在暂停态部署**（本协议全程在暂停态完成） |
| `BattleDeployDirectionRectMove` | `rectMove [-48,-48,96,96]` | 第 ② 段"拖动菱形定朝向" |
| `BattleOperAvatar` | `rectMove [7,32,60,60]` | 卡片中心 → 头像区（用于识别卡片） |
| `BattleOperCost` | `rectMove [-10,12,30,17]` | 卡片中心 → 费用数字（用于读取卡片费用） |
| `BattleCancelSelection` | `ClickRect [630,0,20,20]` | 取消误选 |

## 四、实测坐标（1920×1080，1-1 演习）

| 元素 | 帧坐标 |
|---|---|
| 待部署卡片中心（第 n 张） | 12 张卡片的中心 x ≈ 87, 242, 387, 551, 719, 891, 1036, 1262, 1369, 1527, 1689, 1855；y ≈ 995 |
| 暂停按钮 | ≈(1877, 76)（MAA `BattleHasStarted` 换算为 ≈(1807,79)，两者均可触发，热区较宽） |
| 绿色可部署高亮区 | 帧 x≈990~1710、y≈180~810（随关卡地图不同） |
| 朝向菱形 | 部署后出现在格子上，四角对应四方向（实测中心 (1063,252)、下角 (1063,396)） |

## 五、下一步
1. 把本协议封装为 `plugins/action/deploy.py` 的可复用函数（`deploy(card_index, grid_xy, direction)`）；
2. 部署前后各读一次**费用**与**费用条相位**，产出**实机事件帧**（部署时刻）；
3. 与模拟器 `events.py` 的事件时间线**逐帧对照**；
4. 同样方式打通**技能**与**撤退**。
'''

io.open(DOC, 'w', encoding='utf-8').write(MD)
print('已写出部署协议:', DOC)

ADD = (' **★★★重大突破：战斗内部署协议打通（2026-09-15）**：'
       '①**部署＝两段 motionevent 拖拽序列**（全程在**暂停态**完成，对应 MAA `BattleDeployWhenPause`）：'
       '(a) `DOWN(卡片) → MOVE(中间点×2) → UP(目标格子)` ⇒ 进入**朝向选择态**（出现白色菱形选择框 + 红色"点击取消"）；'
       '(b) `DOWN(菱形中心) → MOVE → UP(目标方向的角)` ⇒ **部署完成**；'
       '②**成功判据三重，实测全部成立**：干员出现在战场 ✅、**底部对应卡片消失（12→11 张）** ✅、'
       '**"剩余可放置角色"计数 8→7** ✅；'
       '③**关键坑（全部踩过并定位）**：`input tap` 点卡片会被判为**长按**（弹出干员详情面板，'
       '但同时**证明点击被接受**且地图出现**绿色可部署高亮格**）；`input tap` 点绿格 ❌；'
       '`input swipe` 卡片→格子（600/1000ms）❌；`motionevent DOWN+UP` 快速单击 ❌；'
       '**只有"带中间点的 motionevent 拖拽序列"才被游戏识别** ⇒ 这是本项目"关卡内操作"的关键发现；'
       '④**与 MAA 定义对应**：`BattleDeployWhenPause`（暂停态部署）、'
       '`BattleDeployDirectionRectMove: [-48,-48,96,96]`（拖动定朝向）、'
       '`BattleOperAvatar/BattleOperCost`（卡片中心→头像/费用数字的偏移，用于识别卡片）、'
       '`BattleCancelSelection: ClickRect [630,0,20,20]`（取消误选）；'
       '⑤**产出 `knowledge/04/49_战斗内操作协议_部署.md`**（含协议、判据、坑、实测坐标表：'
       '12 张卡片中心 x≈87/242/387/551/719/891/1036/1262/1369/1527/1689/1855，y≈995）；'
       '⑥**下一步**：(a) 封装为 `plugins/action/deploy.py` 的可复用函数；'
       '(b) 部署前后各读费用与相位，产出**实机部署事件帧**；'
       '(c) 与模拟器 `events.py` 的时间线**逐帧对照**；(d) 同法打通**技能**与**撤退**；'
       '⑦**合规**：全程演习（零理智）；仅图形界面级操控；未触碰游戏文件/内存。 | 2026-09-15 |')

r = io.open(REG, encoding='utf-8').read()
ra = '\n\n## 冲突记录'
r = r.replace(ra, ADD + ra, 1)
io.open(REG, 'w', encoding='utf-8', newline='').write(r)
print('台账已记录')
shutil.copy2(DOC, os.path.join(DST, 'knowledge', '04_数据对应与核验', os.path.basename(DOC)))
shutil.copy2(REG, os.path.join(DST, 'management', 'tasks_registry.md'))
print('同步完成')
