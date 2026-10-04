# -*- coding: utf-8 -*-
"""append_deploy_verified.py — ★★部署协议完全验证 + 封装。"""
import io
import os
import shutil
import sys

sys.stdout.reconfigure(encoding='utf-8')

REG = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
DOC = r'C:\Users\23922\Documents\ds_harness\ak\knowledge\04_数据对应与核验\49_战斗内操作协议_部署.md'
DST = r'E:\__file\ak_kb\kb'

ADD = (' **★★部署协议完全验证（2026-09-15，第二次成功，三重确证）**：'
       '①**成功证据（全部成立）**：**费用 15 → 8（恰好扣掉第一张卡片的 7 费）**、'
       '**「剩余可放置角色」8 → 7**、**底部第一张卡片（费用 7）消失** ⇒ 部署协议**可靠可用**；'
       '②**最终协议（暂停态执行，对应 MAA `BattleDeployWhenPause`）**：'
       '**第 1 段**：`motionevent DOWN(卡片中心) → MOVE(中间点×2) → MOVE(目标格) → UP(目标格)` '
       '⇒ 进入**朝向选择态**（画面出现白色粗边框菱形 + 红色「点击取消」）；'
       '**第 2 段**：`motionevent DOWN(菱形中心) → MOVE → UP(目标方向的角)` ⇒ **部署完成**；'
       '③**★关键修正（本轮踩坑）**：**朝向菱形的中心 = 游戏「吸附后」的干员位置，不是拖拽落点坐标** —— '
       '实测拖到 (1200,400)、游戏把干员吸附到格心 **(1063,333)**，必须**以菱形中心为起点**拖朝向；'
       '用落点坐标拖会失败（此前两次失败的根因之一）；'
       '④**另一根因**：**费用不足时游戏完全不接受拖拽**（本轮费用仅 8 而下一张卡需 9 费 ⇒ 拖拽无任何反应、'
       '菱形检测返回 None）⇒ 部署前**必须先校验费用 ≥ 卡片费用**；'
       '⑤**封装产出 `plugins/action/deploy.py`（`Deployer` 类）**：'
       '`motion(points)`（motionevent 序列）、`pause()/resume()`、`read_cost()`（费用+相位，'
       '用于产出实机事件帧）、**`find_diamond()`（阈值+轮廓检测白色菱形）**、'
       '**`set_direction(diamond, direction)`（按检测到的菱形拖朝向）**、'
       '`deploy(card_xy, grid_xy, direction)`、**`deploy_timed(...)`（部署前后读数 ⇒ 事件帧记录）**、'
       '`retreat()/skill()`（入口已留，待标定）；'
       '附 `card_centers()` 给出实测的 12 张卡片中心 x；'
       '⑥**待办**：(a) 菱形检测的阈值/面积参数需在"确实进入朝向态"的画面下再校准；'
       '(b) 用 `deploy_timed` 产出**实机部署事件帧**并与模拟器 `events.py` 的时间线对照；'
       '(c) 同法打通**技能**与**撤退**；'
       '⑦**合规**：全程演习（零理智）；仅图形界面级操控；未触碰游戏文件/内存。 | 2026-09-15 |')

r = io.open(REG, encoding='utf-8').read()
ra = '\n\n## 冲突记录'
r = r.replace(ra, ADD + ra, 1)
io.open(REG, 'w', encoding='utf-8', newline='').write(r)
print('台账已记录')

# 更新协议文档
extra = '''

---

## 六、★最终协议（第二次成功，三重确证）2026-09-15

**成功证据**：费用 15→8（恰好扣掉第一张卡片的 7 费）、「剩余可放置角色」8→7、第一张卡片消失。

**关键修正（两次失败的根因）**：
1. **朝向菱形的中心 = 游戏「吸附后」的干员位置**，**不是拖拽落点**！
   实测拖到 (1200,400)，游戏吸附到格心 **(1063,333)**，必须以菱形中心为起点拖朝向。
2. **费用不足时游戏完全不接受拖拽**（费用 8 < 下一张卡 9 费 ⇒ 无反应、菱形检测返回 None）
   ⇒ 部署前先校验 `费用 ≥ 卡片费用`。

**封闭式协议**：
```
0. 校验：费用 ≥ 卡片费用；游戏处于暂停态
1. motionevent DOWN  <卡片中心>
   motionevent MOVE  <中间点×2>
   motionevent MOVE  <目标格>
   motionevent UP    <目标格>          ⇒ 进入朝向态（白色菱形 + 点击取消）
2. 检测菱形（白框、面积大、近似正方形）得到 (cx,cy,w,h)
3. motionevent DOWN  <(cx,cy)>
   motionevent MOVE  <向目标方向 r/2>
   motionevent UP    <(cx±r, cy) 或 (cx, cy±r)>，r ≈ 0.45h   ⇒ 部署完成
```

**封装**：`plugins/action/deploy.py`（`Deployer`：`motion/pause/resume/read_cost/find_diamond/set_direction/deploy/deploy_timed`）。
'''
s = io.open(DOC, encoding='utf-8').read()
if '六、★最终协议' not in s:
    io.open(DOC, 'a', encoding='utf-8').write(extra)
    print('已更新协议文档')
shutil.copy2(DOC, os.path.join(DST, 'knowledge', '04_数据对应与核验', os.path.basename(DOC)))
d = os.path.join(DST, r'code\vision\plugins\action\deploy.py')
os.makedirs(os.path.dirname(d), exist_ok=True)
shutil.copy2(r'C:\Users\23922\Documents\ds_harness\ak\code\vision\plugins\action\deploy.py', d)
shutil.copy2(REG, os.path.join(DST, 'management', 'tasks_registry.md'))
print('同步完成')
