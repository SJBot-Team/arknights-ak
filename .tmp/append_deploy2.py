# -*- coding: utf-8 -*-
"""append_deploy2.py — 部署流程的完整诊断与下轮行动。"""
import io
import os
import shutil
import sys

sys.stdout.reconfigure(encoding='utf-8')

REG = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
DST = r'E:\__file\ak_kb\kb'

ADD = (' **战斗内部署：完整诊断（2026-09-15）**：'
       '①**已确认可用的环节**（1-1 演习战斗）：进战斗 ✅、**暂停 ✅**（PAUSE/暂停中）、'
       '**费用尺读取 ✅**（cost=22/tick=11，与画面一致）、**待部署区 12 张卡片识别 ✅**'
       '（费用 7/9/9/10/11/11/12/18/22/22/22/22）；'
       '②**★关键发现：点卡片是生效的** —— 用 `input tap` 点卡片后，**左侧弹出干员详情面板**'
       '（实测弹出「魔王 LV61 攻击378 防御220 法抗0 阻挡1 技能:明日渺远不及」），'
       '**且战场地图上出现绿色高亮格**（= 游戏的"选择中/可部署"提示）'
       '⇒ **证明点击被游戏接受、且进入了选择态**；'
       '③**未完成的环节与原因推断**：点绿色高亮格、`motionevent DOWN/UP` 快速点击、'
       '`input swipe` 拖拽**均未完成部署**（费用未被扣、场上无新单位）；'
       '对照 MAA 的定义可知**流程还差最后一步**：'
       '**`BattleDeployDirectionRectMove`: `rectMove [-48,-48,96,96]`** ⇒ '
       '**AK 的部署＝「点卡片选中 → 点/拖到格子 → 拖动以确定朝向」**，'
       '**我此前缺少"拖动定朝向"这一步**，因此部署未提交；'
       '（另注意 `input tap` 时长会被游戏判为长按而弹出详情，说明**点击时长需要介于'
       '"长按"与"过短"之间**，或需要"按下-拖动-抬起"完整序列）'
       '④**旁证**：`BattleDeployWhenPause`（`specialParams [1]`）表明 **MAA 在暂停态做部署**，'
       '而 `BattleCancelSelection`（`ClickRect [630,0,20,20]`）用于取消误选；'
       '⑤**下一轮行动（明确）**：(a) 进 1-1 演习 → 暂停；'
       '(b) 用**"按下(卡片) → 移动到格子 → 抬起"**的完整拖拽序列（`input swipe` 用 400~600ms，'
       '并在抬起点附近**再发一次小幅移动**以触发朝向选择）；'
       '(c) 或按"点选式"：点卡片 → 点格子 → **在格子上做一次短拖动**（约 96px 见方，照 MAA 的 rectMove）；'
       '(d) 部署成功后立即记录 **cost 变化帧、单位出现帧、朝向**，用于与模拟器事件时间线对齐；'
       '⑥**合规**：全程演习（零理智）；仅图形界面级操控；未触碰游戏文件/内存。 | 2026-09-15 |')

r = io.open(REG, encoding='utf-8').read()
ra = '\n\n## 冲突记录'
r = r.replace(ra, ADD + ra, 1)
io.open(REG, 'w', encoding='utf-8', newline='').write(r)
print('台账已记录')
shutil.copy2(REG, os.path.join(DST, 'management', 'tasks_registry.md'))
print('同步完成')
