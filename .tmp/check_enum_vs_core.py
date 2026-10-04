# -*- coding: utf-8 -*-
"""枚举词典里的“官方用词” vs 核心区名词对照表里的用词：找出不一致，供区分「官方命名 / 玩家俗称」。只读。"""
import csv
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
A = r'C:\Users\23922\Documents\ds_harness\ak'
G = os.path.join(A, 'glossary')
K = os.path.join(A, 'knowledge', '07_名词对照')

# 1) 枚举词典里的中文（官方/社区解包用词）
enum = list(csv.reader(open(os.path.join(G, '05_枚举词典.tsv'), encoding='utf-8'), delimiter='\t'))[1:]
terms = {}
for r in enum:
    if len(r) < 8:
        continue
    zh, code, cat = r[1], r[2], r[7]
    terms.setdefault(zh, []).append(f'{cat}.{code}')
print(f'枚举词典：{len(enum)} 条，去重中文词 {len(terms)} 个')

# 2) 核心区出现的中文机制词（从 01/02/04 的“官方汉语命名/官方名”列抓）
core = {}
for fn in ('01_机制与概念.md', '02_代码层命名对照.md', '04_玩家黑话与自限玩法.md'):
    p = os.path.join(K, fn)
    if not os.path.exists(p):
        continue
    for line in open(p, encoding='utf-8'):
        if not line.startswith('|'):
            continue
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        if len(cells) < 7 or cells[0] in ('汉语拼音',) or cells[0].startswith('---'):
            continue
        name = re.sub(r'[`*]', '', cells[1])
        core.setdefault(name, fn)
print(f'核心区词条：{len(core)} 个中文名')

# 3) 找“同一个概念、两种写法”的候选：枚举词典里的词 与 核心区词 有包含关系但不是完全相同
pairs = []
for zh, codes in terms.items():
    if zh in core:
        continue
    hits = [c for c in core if (c in zh or zh in c) and len(c) >= 2 and len(zh) >= 2]
    for h in hits:
        pairs.append((zh, ','.join(codes[:2]), h, core[h]))
print(f'\n可能的同义/异写配对 {len(pairs)} 组（枚举词典用词 ↔ 核心区用词）：')
for zh, code, h, fn in sorted(pairs)[:40]:
    print(f'  {zh:12} [{code:28}] ↔ 核心区「{h}」({fn})')
