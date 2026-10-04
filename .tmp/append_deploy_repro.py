# -*- coding: utf-8 -*-
"""append_deploy_repro.py — 部署复现条件的精确界定（含 TR-1 练手环境发现）。"""
import io
import os
import shutil
import sys

sys.stdout.reconfigure(encoding='utf-8')

REG = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
DOC = r'C:\Users\23922\Documents\ds_harness\ak\knowledge\04_数据对应与核验\49_战斗内操作协议_部署.md'
DST = r'E:\__file\ak_kb\kb'

ADD = (' **部署复现条件的精确界定 + TR-1 练手环境（2026-09-15）**：'
       '①**★发现理想的练手环境：TR-1「战地医疗」训练关** —— **理智消耗 0**（训练关免费，"演习"按钮因此被禁用）、'
       '**仅 5 个敌人**、**固定编队不可改**（巡林者/芙蓉/夜刀，均为低星满配）、'
       '入口：主界面 → 终端 → 序章地图 EP00（0-1 / **TR-1** / 0-2）→ 点 TR-1 → 「开始行动」；'
       '⇒ 满足用户"挑选满配干员尝试第 1 章简单关卡"的要求，且**零消耗、可无限重复**，最适合练手与回归测试；'
       '②**新增/固化的能力**（`plugins/action/deploy.py`）：'
       '(a) **`ensure_paused()`**：**先判定界面必须是 battle**，再用"两次读数（费用+相位）都不变"确认暂停 —— '
       '修掉了此前把"非战斗静止画面（如关卡地图）"误判为暂停的问题；实测在 TR-1 战斗中返回 '
       '`True {cost:15, fill_px:180, tick:29}` 正确；'
       '(b) **`frame_of(cost, tick, initial_cost=10)`**：把实机读数换算成**游戏内帧**（`(cost-init)*30+tick`），'
       '实测 `frame_of(15,21)=171`、`frame_of(15,29)=179`，与模拟器同一时间轴；'
       '(c) **`is_paused()`**、`deploy(preselect=True)`（先点卡片建立选择态）；'
       '③**部署复现的现状（问题已精确界定）**：'
       '**协议方向已两次验证成功**（见 §六：费用 15→8 恰好扣 7、可放置数 8→7、卡片消失，三重判据全中），'
       '**但复现条件尚未完全锁定** —— 本轮在 1-1 与 TR-1 上用相同序列多次尝试均未进入朝向态'
       '（`find_diamond()` 返回 None、费用未变）；'
       '**已测试并排除**：`input tap` 点卡片（会弹详情，但确实被接受）、`input tap` 点格子、'
       '`input swipe` 拖拽、`motionevent DOWN+UP`（太短）、不同格子坐标、不同关卡（1-1 / TR-1）、'
       '资金不足（已验证费用充足时仍失败）；'
       '**待验证的关键假设**：'
       '(a) **"先 tap 卡片弹出的详情面板"是否阻挡了随后的拖拽** —— 成功案例中 tap 与拖拽之间隔了一次截图，'
       '面板可能已收起；本轮 `preselect` 仅等 1.2s；'
       '(b) **选中态的视觉确认**：应在 tap 卡片后**截图确认"绿色可部署高亮格"确实出现**，再执行拖拽；'
       '(c) 暂停态的"可交互性"是否稳定（本轮多次出现"点击暂停后费用仍在涨"）；'
       '④**下一步（建议的排查方式）**：把部署拆成**四个可独立验证的小步**，每步截图确认后再进行下一步：'
       '**步1 暂停确认**（`ensure_paused` ⇒ 已可用）→ **步2 点卡片并确认绿格出现**（需加"绿色高亮检测"）'
       '→ **步3 拖拽到绿格并确认菱形出现**（`find_diamond`）→ **步4 拖菱形并确认费用扣除**；'
       '任一步的截图都能定位失败点；'
       '⑤**合规**：全程演习/训练关（零理智）；仅图形界面级操控；未触碰游戏文件/内存。 | 2026-09-15 |')

r = io.open(REG, encoding='utf-8').read()
ra = '\n\n## 冲突记录'
r = r.replace(ra, ADD + ra, 1)
io.open(REG, 'w', encoding='utf-8', newline='').write(r)
print('台账已记录')

extra = '''

---

## 七、部署复现：问题界定与四步排查法（2026-09-15）

**协议方向已两次成功**（§六 三重判据），**但复现条件未完全锁定**。本轮在 1-1 与 TR-1 上以相同序列多次尝试均未进入朝向态。

**已测试并排除的做法**：`input tap` 点卡片 / `input tap` 点格子 / `input swipe` 拖拽 / `motionevent DOWN+UP` /
不同格子坐标 / 不同关卡 / 费用不足（费用充足时同样失败）。

**待验证的关键假设**：
1. **tap 卡片后弹出的详情面板是否阻挡了随后的拖拽**（成功案例中 tap 与拖拽之间隔了一次截图，面板可能已收起）；
2. **选中态缺少视觉确认** —— 应在 tap 卡片后确认"绿色可部署高亮格"出现，再进行拖拽；
3. 暂停态的"可交互性"是否稳定（本轮多次出现"点了暂停但费用仍在涨"）。

**建议的四步排查法**（每步截图确认后再进行下一步）：

| 步 | 动作 | 确认方式 |
|---|---|---|
| 1 | `ensure_paused()` | 返回 True 且界面为 battle（**已可用**） |
| 2 | 点卡片 | **截图确认"绿色可部署高亮格"出现**（需新增"绿色高亮检测"） |
| 3 | 拖拽卡片到绿格 | **`find_diamond()` 返回菱形** |
| 4 | 拖菱形定朝向 | **费用扣除 / 卡片消失 / 可放置数 −1** |

任一步的截图都能定位失败点，避免再次"整段失败却不知在哪一步"。

**理想练手环境（本轮发现）**：**TR-1「战地医疗」训练关** —— 理智 0、仅 5 敌人、固定编队（巡林者/芙蓉/夜刀），
入口：终端 → 序章 EP00 地图 → TR-1 → 开始行动。
'''
s = io.open(DOC, encoding='utf-8').read()
if '七、部署复现：问题界定与四步排查法' not in s:
    io.open(DOC, 'a', encoding='utf-8').write(extra)
    print('已更新协议文档')
shutil.copy2(DOC, os.path.join(DST, 'knowledge', '04_数据对应与核验', os.path.basename(DOC)))
d = os.path.join(DST, r'code\vision\plugins\action\deploy.py')
os.makedirs(os.path.dirname(d), exist_ok=True)
shutil.copy2(r'C:\Users\23922\Documents\ds_harness\ak\code\vision\plugins\action\deploy.py', d)
shutil.copy2(REG, os.path.join(DST, 'management', 'tasks_registry.md'))
print('同步完成')
