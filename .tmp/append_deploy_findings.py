# -*- coding: utf-8 -*-
"""append_deploy_findings.py — 战斗内部署的尝试与 MAA 定义发现。"""
import io
import os
import shutil
import sys

sys.stdout.reconfigure(encoding='utf-8')

REG = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
DOC = r'C:\Users\23922\Documents\ds_harness\ak\knowledge\04_数据对应与核验\48_MAA方案索引_关卡外流程.md'
DST = r'E:\__file\ak_kb\kb'

ADD = (' **战斗内部署：尝试记录与 MAA 定义发现（2026-09-15）**：'
       '①**已完成的验证**（1-1 演习战斗）：进入战斗后**暂停成功**（PAUSE/暂停中 + 演习中横幅）；'
       '**费用尺读取成功**（cost=22、fill_px=69、tick=11，与画面一致）；'
       '**待部署区识别**（12 张卡片、费用 7/9/9/10/11/11/12/**18(令)**/22/22/22/22）；'
       '②**部署尝试均未成功**（三种方式）：(a) 运行态点卡片(67,981)+点格 ⇒ 未部署；'
       '(b) 运行态点卡片(1165,1023)+点高台格(1666,411) ⇒ 未部署；'
       '(c) 暂停态点卡片(1036,1020) 再恢复+点格 ⇒ 未部署；(d) **拖拽**（卡片→格子，600ms）'
       '⇒ 随后画面全黑（该局已因漏怪失败/进入结算，生命 10→6→0）；'
       '**⇒ 战斗中「部署」这一环尚未打通（本轮遗留的首要问题）**；'
       '③**MAA 的关键定义（照抄，来源 tasks.json）**：'
       '**`BattleDeployWhenPause`：`{"algorithm":"JustReturn","specialParams":[1]}`** ⇒ '
       '**MAA 正是在"暂停时"做部署**（该标志交给它的 C++ 核心执行）⇒ 印证 prts+ 的"子弹时间"思路；'
       '`BattleDeployDirectionRectMove`：`rectMove [-48,-48,96,96]`（部署后**拖动调朝向**）；'
       '`BattleOperAvatar`：`rectMove [7,32,60,60]`（卡片中心→头像区）；'
       '`BattleOperCost`：`rectMove [-10,12,30,17]`（卡片中心→费用数字）；'
       '`BattleCancelSelection`：**`ClickRect`，`specificRect [630,0,20,20]`**（取消当前选择）；'
       '**`BattleHasStarted`：`roi [1178,33,53,39]`（暂停按钮），Doc 原文「20260109 YJWL更新后'
       '暂停按钮向右移动约8像素, 且暂停后亮度上限245」** ⇒ 换算 @1920 暂停按钮约 (1767,50)-(1847,108)、中心 ≈(1807,79)'
       '（我此前用的 (1877,76) 偏右约 70px，但实测仍能触发暂停，说明按钮热区较宽）；'
       '④**下一步（断点）**：(a) **重进 1-1 演习**，**先暂停**，再用 MAA 推算的卡片中心坐标（含 `BattleOperCost`/'
       '`BattleOperAvatar` 的偏移关系）**逐张定位并试部署**，每次操作后**截图确认选中态**（卡片高亮/格子高亮）；'
       '(b) 若"点选式"仍不通，改用**暂停态拖拽**（`BattleDeployWhenPause` 思路）并配合 `BattleDeployDirectionRectMove` 定朝向；'
       '(c) 部署成功后立即记录 **cost 变化帧** 与 **单位出现帧**，用于与模拟器事件时间线对齐；'
       '⑤**合规**：全程演习（零理智）；仅图形界面级操控；未触碰游戏文件/内存。 | 2026-09-15 |')

r = io.open(REG, encoding='utf-8').read()
ra = '\n\n## 冲突记录'
r = r.replace(ra, ADD + ra, 1)
io.open(REG, 'w', encoding='utf-8', newline='').write(r)
print('台账已记录')

extra = '''

---

## 十一、战斗内（关卡内）操作：MAA 定义（战斗不适用"关卡外严格照 MAA"的同一套，但定义可照抄）

| 任务 | 定义（来源 `tasks.json`） | 含义 |
|---|---|---|
| **`BattleDeployWhenPause`** | `{"algorithm":"JustReturn","specialParams":[1]}` | **在暂停时部署**（MAA 交其 C++ 核心执行）⇒ 与 prts+ 的"子弹时间"同源 |
| `BattleDeployDirectionRectMove` | `rectMove [-48,-48,96,96]` | 部署后**拖动调朝向** |
| `BattleOperAvatar` | `rectMove [7,32,60,60]` | 卡片中心 → 头像区域 |
| `BattleOperCost` | `rectMove [-10,12,30,17]` | 卡片中心 → 费用数字 |
| `BattleOperAvailable` | `specialParams [100]`（V 通道均值阈值），`rectMove [0,0,10,10]` | 判定卡片是否可用（费用够/未冷却） |
| `BattleCancelSelection` | `{"action":"ClickRect","specificRect":[630,0,20,20]}` | 取消当前选择 |
| `BattleHasStarted` | `roi [1178,33,53,39]`；Doc：「**20260109 YJWL更新后暂停按钮向右移动约8像素, 且暂停后亮度上限245**」 | 判定已进入战斗 + 暂停按钮位置 |
| `BattleOperRetreat` / `BattleOperRetreatJustClick` | — | 撤退 |
| `BattleOfficiallyBegin` / `BattleHpFlag` / `BattleCostFlag` / `BattleKillsFlag` | 已用于我方 `ui_state`（battle 判定） | 战斗界面判定 |

**本轮实测结论**：`cost` 读取✅、暂停✅、待部署区卡片识别✅，但**"部署"动作尚未打通**（点选式与拖拽式各试 2 次均未生效）⇒ 下一轮优先解决。
'''
s = io.open(DOC, encoding='utf-8').read()
if '十一、战斗内（关卡内）操作' not in s:
    io.open(DOC, 'a', encoding='utf-8').write(extra)
    print('已补充 MAA 索引')
shutil.copy2(DOC, os.path.join(DST, 'knowledge', '04_数据对应与核验', os.path.basename(DOC)))
shutil.copy2(REG, os.path.join(DST, 'management', 'tasks_registry.md'))
print('同步完成')
