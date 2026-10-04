# -*- coding: utf-8 -*-
"""把 knowledge/01_基础数据/01_数据基础_属性与伤害公式.md 按预定的下沉方案拆成 01a / 01b。
正文逐字搬运（不改写、不丢行），只在每个子文件头部加"子文件"标识块。
"""
import os

BASE = r'C:\Users\23922\Documents\ds_harness\ak\knowledge\01_基础数据'
SRC = os.path.join(BASE, '01_数据基础_属性与伤害公式.md')
A = os.path.join(BASE, '01a_属性伤害与数值公式_公式与规则.md')
B = os.path.join(BASE, '01b_基础数据_数值表与伤判基建.md')

raw = open(SRC, 'rb').read()
bom = raw.startswith(b'\xef\xbb\xbf')
text = raw.decode('utf-8-sig')
lines = text.split('\n')

assert lines[10].startswith('## 1. 属性体系'), lines[10][:40]
assert lines[116].startswith('## 7. 阻挡半径'), lines[116][:40]
assert lines[6].startswith('## 0.'), lines[6][:40]

a_body = '\n'.join(lines[10:116]).rstrip('\n')
b_body = '\n'.join(lines[116:]).strip('\n')

PARENT = ('> **本文件是 `01_数据基础_属性与伤害公式.md` 的**子文件**（母文件：`knowledge/01_基础数据/01_数据基础_属性与伤害公式.md`）。\n'
          '> 来源与置信度标注同母文件（PRTS「游戏数据基础」，抓取 2026-08-31）。\n'
          '> 拆分日期：2026-09-23（T-062 结构治理）——**正文逐字搬运，未改写**；母文件只保留结论地图与地址。\n')

a_head = ('# 01a 数据基础：属性、伤害与数值公式 —— **公式与规则**\n\n'
          + PARENT +
          '> 本篇内容：**§1 属性体系 · §2 倍率 · §3 伤害公式 · §4 攻速 · §5 重量与位移 · §6 移速**。\n'
          '> 数值表 / 伤判 / 基建 / 待补项见 `01b_基础数据_数值表与伤判基建.md`。\n\n---\n\n')

b_head = ('# 01b 数据基础：**数值表、伤判、基建**\n\n'
          + PARENT +
          '> 本篇内容：**§7 阻挡半径 · §8 闪避 · §9 维持技能 · §10 基建数值 · §11 待补 · §12 各子页面精确数值（§12.1~§12.11）**。\n'
          '> 公式与规则见 `01a_属性伤害与数值公式_公式与规则.md`；母文件（结论地图）见 `01_数据基础_属性与伤害公式.md`。\n\n---\n\n')

enc = 'utf-8-sig' if bom else 'utf-8'
open(A, 'w', encoding=enc, newline='\n').write(a_head + a_body + '\n')
open(B, 'w', encoding=enc, newline='\n').write(b_head + b_body + '\n')

for f in (A, B):
    n = open(f, encoding='utf-8-sig').read().count('\n') + 1
    print(f'{os.path.basename(f)}: {n} 行, {os.path.getsize(f)} B')
print('母文件原样保留（稍后手工改写）:', len(lines), '行')
