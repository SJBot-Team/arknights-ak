# -*- coding: utf-8 -*-
"""从敌人表里统计「命名族」与图鉴号体系，供核心区写「敌人命名规律」。只读。"""
import collections
import csv
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
G = r'C:\Users\23922\Documents\ds_harness\ak\glossary'
rows = list(csv.reader(open(os.path.join(G, '03_敌人.tsv'), encoding='utf-8'), delimiter='\t'))[1:]
recs = [(r[2], r[1], r[7] if len(r) > 7 else '', r[8] if len(r) > 8 else '') for r in rows if len(r) > 2]
print('敌人总数', len(recs))

# 1) ID 家族：去掉末尾 _数字
fam = collections.defaultdict(list)
for eid, name, idx, lvl in recs:
    base = re.sub(r'_\d+$', '', eid)
    fam[base].append(name)
print('\n== 成员最多的 18 个 ID 家族 ==')
for base, names in sorted(fam.items(), key=lambda kv: -len(kv[1]))[:18]:
    print(f'  {base:34} {len(names):3} 个   例: {" / ".join(names[:3])}')

# 2) 图鉴号前缀（enemyIndex）分布
pref = collections.Counter(re.match(r'^[A-Za-z]*', idx or '').group(0) for _, _, idx, _ in recs)
print('\n== 图鉴号(enemyIndex)前缀分布（前 15） ==')
for k, v in pref.most_common(15):
    print(f'  {k or "(空)":8} {v}')

# 3) 等级枚举
lvl = collections.Counter(l for _, _, _, l in recs)
print('\n== 等级(enemyLevel) ==', dict(lvl))
