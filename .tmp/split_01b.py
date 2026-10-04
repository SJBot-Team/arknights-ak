# -*- coding: utf-8 -*-
"""第二刀：01b（699 行，仍 >600 行红线）再拆为
   01b_战斗机制补充_阻挡闪避伤判与费用.md  ← §7~§9 + §12.6~§12.11
   01c_数值表与基建_成长等级信赖.md        ← §10~§12.5
正文逐字搬运。
"""
import os

BASE = r'C:\Users\23922\Documents\ds_harness\ak\knowledge\01_基础数据'
OLD = os.path.join(BASE, '01b_基础数据_数值表与伤判基建.md')
NEW_B = os.path.join(BASE, '01b_战斗机制补充_阻挡闪避伤判与费用.md')
NEW_C = os.path.join(BASE, '01c_数值表与基建_成长等级信赖.md')

text = open(OLD, encoding='utf-8-sig').read()
lines = text.split('\n')
assert lines[10].startswith('## 7. 阻挡半径'), lines[10][:30]
assert lines[24].startswith('## 10. 基建数值公式'), lines[24][:30]
assert lines[429].startswith('### 12.5'), lines[429][:30]
assert lines[547].startswith('### 12.6'), lines[547][:30]

seg_a = '\n'.join(lines[10:24]).strip('\n')      # §7~§9
seg_b = '\n'.join(lines[24:547]).strip('\n')     # §10~§12.5
seg_c = '\n'.join(lines[547:]).strip('\n')       # §12.6~§12.11

PARENT = ('> **本文件是 `01_数据基础_属性与伤害公式.md` 的子文件**（母文件：`knowledge/01_基础数据/01_数据基础_属性与伤害公式.md`）。\n'
          '> 来源与置信度标注同母文件（PRTS「游戏数据基础」，抓取 2026-08-31）。\n'
          '> 拆分日期：2026-09-23（T-062 结构治理）——**正文逐字搬运，未改写**。\n')

head_b = ('# 01b 数据基础：**战斗机制补充**（阻挡 / 闪避 / 维持技能 / 取整 / 伤判 / 定点 / 生命值 / 费用 / 手牌区）\n\n'
          + PARENT +
          '> 本篇：**§7 阻挡半径 · §8 闪避 · §9 维持技能状态**，以及 **§12.6 就近取整 · §12.7 伤判效果 · §12.8 定点数与浮点数 ·\n'
          '> §12.9 生命值 · §12.10 部署费用（含返费） · §12.11 待部署区**。（原 §12 是子页面抓取汇总，按"机制类 / 数值表类"重新分组）\n'
          '> 公式与规则见 `01a`；**成长曲线与数值范围长表见 `01c`**；母文件（结论地图）见 `01_数据基础_属性与伤害公式.md`。\n\n---\n\n')

head_c = ('# 01c 数据基础：**数值表与基建**（数值范围 / 升级 / 等级上限 / 博士等级 / 信赖 / 基建公式）\n\n'
          + PARENT +
          '> 本篇：**§10 基建数值公式 · §11 其他待补数值 · §12.1 数值范围 · §12.2 干员升级数值 · §12.3 干员等级上限 ·\n'
          '> §12.4 博士等级 · §12.5 信赖值**。**以查表为主**，按小节跳读。\n'
          '> 战斗机制类补充（阻挡/闪避/伤判/定点/生命值/费用/手牌区）见 `01b`；公式见 `01a`；母文件见 `01_数据基础_属性与伤害公式.md`。\n\n---\n\n')

open(NEW_B, 'w', encoding='utf-8', newline='\n').write(head_b + seg_a + '\n\n---\n\n' + seg_c + '\n')
open(NEW_C, 'w', encoding='utf-8', newline='\n').write(head_c + seg_b + '\n')

for f in (NEW_B, NEW_C):
    n = open(f, encoding='utf-8-sig').read().count('\n') + 1
    print(f'{os.path.basename(f)}: {n} 行, {os.path.getsize(f)} B')
