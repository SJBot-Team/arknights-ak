# -*- coding: utf-8 -*-
"""查 h12-4 关卡数据里的「费用上限」相关字段与可摧毁物（街头应急储备）"""
import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
BASE = r'C:\Users\23922\Documents\ds_harness\ak\data\gamedata_akgd'
LV = os.path.join(BASE, 'levels', 'obt', 'hard', 'level_hard_12-04.json')
if not os.path.exists(LV):
    import glob
    cand = glob.glob(os.path.join(BASE, '**', '*12-04*.json'), recursive=True)
    print('候选关卡文件:', cand[:5])
    LV = cand[0] if cand else None
if not LV:
    raise SystemExit('找不到关卡文件')

d = json.load(open(LV, encoding='utf-8'))
print('关卡:', d.get('levelId'))
print('options:', json.dumps(d.get('options'), ensure_ascii=False))
print('\n--- runes ---')
print(json.dumps(d.get('runes'), ensure_ascii=False)[:600])
print('\n--- 含 cost 的字面量 ---')
s = json.dumps(d, ensure_ascii=False)
import re
for m in re.finditer(r'.{80}[Cc]ost.{120}', s):
    print('  …', m.group(0).replace('\n', ' '))
    break
keys = set()
for m in re.finditer(r'"([A-Za-z_]*[Cc]ost[A-Za-z_]*)"\s*:', s):
    keys.add(m.group(1))
print('含 cost 的键名:', sorted(keys))
for m in re.finditer(r'"([A-Za-z_]*max[A-Za-z_]*)"\s*:', s, re.I):
    keys.add(m.group(1))
print('\n--- 其他可能相关的键 ---')
for k in ('maxCost', 'initialCost', 'costIncreaseTime', 'maxHp', 'lifePointReduction'):
    if f'"{k}"' in s:
        i = s.index(f'"{k}"')
        print(f'  {k}: …{s[i:i+80]}')
print('\n--- 关卡内的装置/可摧毁物（若有） ---')
for k in ('obstacles', 'devices', 'mapData', 'tiles', 'enemyDbRefs'):
    v = d.get(k)
    print(f'  {k}: {type(v).__name__} len={len(v) if hasattr(v, "__len__") else "-"}')
