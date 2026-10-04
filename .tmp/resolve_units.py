# -*- coding: utf-8 -*-
"""按名字在批量表里反查 ID（只读）。用于把 knowledge/07 里「ID 待补」的单位补全。"""
import csv
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
G = r'C:\Users\23922\Documents\ds_harness\ak\glossary'


def load(n):
    return list(csv.reader(open(os.path.join(G, n), encoding='utf-8'), delimiter='\t'))[1:]


ops = load('01_干员.tsv')
alias = load('02_干员名别名.tsv')
enemies = load('03_敌人.tsv')

NAMES = ['令', '蕾缪安', '弦惊', '莱伊', '山', '黍', '芬', '乌莉卡', '猎狗', '源石虫',
         '霜星', '弑君者', '凯尔希', '玛恩纳', '风笛', '闪灵', '夜莺', '银灰', '陈', '阿米娅',
         '乌尔比安', '德克萨斯', '能天使', '安洁莉娜', '杰西卡', '杜宾', '斯卡蒂', '梅兰莎']


def cells(r, i, d=''):
    return r[i] if len(r) > i else d


for n in NAMES:
    e = [r for r in ops if cells(r, 1) == n]
    a = [r for r in alias if cells(r, 1) == n]
    s = [r for r in ops if n in cells(r, 1) and cells(r, 1) != n][:5]
    ee = [r for r in enemies if cells(r, 1) == n]
    es = [r for r in enemies if n in cells(r, 1) and cells(r, 1) != n][:5]
    parts = []
    if e:
        parts.append('干员 ' + ', '.join(f'{cells(r,2)}({cells(r,10)}{cells(r,11)})' for r in e))
    if a:
        parts.append('别名 ' + ', '.join(cells(r, 2) for r in a[:3]))
    if ee:
        parts.append('敌人 ' + ', '.join(f'{cells(r,2)}({cells(r,7)})' for r in ee[:3]))
    if s:
        parts.append('近似干员 ' + ', '.join(cells(r, 1) for r in s))
    if es:
        parts.append('近似敌人 ' + ', '.join(cells(r, 1) for r in es))
    print(f'{n:6} | ' + (' ; '.join(parts) if parts else '❌ 未命中'))
