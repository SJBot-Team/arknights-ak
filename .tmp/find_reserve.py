# -*- coding: utf-8 -*-
"""找 h12-4 里「街头应急储备」这类可摧毁物的数据（mapData / predefines / 装置表）"""
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
LV = r'E:\__file\ak_kb\gamedata\levels\obt\hard\level_hard_12-04.json'
d = json.load(open(LV, encoding='utf-8'))

mp = d.get('mapData') or {}
print('mapData keys:', list(mp.keys()))
for k, v in mp.items():
    t = type(v).__name__
    n = len(v) if hasattr(v, '__len__') else '-'
    print(f'  {k}: {t} len={n}')
    if isinstance(v, list) and v:
        print('    样例:', json.dumps(v[0], ensure_ascii=False)[:220])

pd = d.get('predefines') or {}
print('\npredefines keys:', list(pd.keys()))
for k, v in pd.items():
    print(f'  {k}: {json.dumps(v, ensure_ascii=False)[:200]}')

s = json.dumps(d, ensure_ascii=False)
print('\n含 obstacle/device/trap/reserve 字样:')
for kw in ('obstacle', 'Obstacle', 'device', 'trap', 'Trap', 'reserve', 'Reserve', 'cbuff'):
    for m in re.finditer(kw, s):
        i = m.start()
        print(f'  [{kw}] …{s[max(0,i-100):i+140]}'.replace('\n', ' '))
        break

# 关卡里出现的所有 key 名（mapData 之外）
print('\n顶层键:', list(d.keys()))
