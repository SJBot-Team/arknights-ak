# -*- coding: utf-8 -*-
"""查 h12-4 关卡数据：费用上限 / runes / 可摧毁储备物"""
import json
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
F = r'E:\__file\ak_kb\gamedata\levels\obt\hard\level_hard_12-04.json'
d = json.load(open(F, encoding='utf-8'))
print('levelId:', d.get('levelId'))
print('options:', json.dumps(d.get('options'), ensure_ascii=False))
print('runes:', json.dumps(d.get('runes'), ensure_ascii=False)[:400])
s = json.dumps(d, ensure_ascii=False)
keys = sorted(set(re.findall(r'"([A-Za-z_]*(?:[Cc]ost|max|Max)[A-Za-z_]*)"\s*:', s)))
print('\n相关键名及片段:')
for k in keys[:24]:
    i = s.find(f'"{k}"')
    print(f'  {k:<22} …{s[i:i+70]}'.replace('\n', ' '))
print('\n关卡内结构:')
for k in ('mapData', 'enemyDbRefs', 'routes', 'waves', 'obstacles', 'devices', 'predefines',
          'tilesDisallowToLocate', 'envSystemConfig', 'runes', 'hardMode'):
    v = d.get(k)
    if v is None:
        continue
    print(f'  {k}: {type(v).__name__} len={len(v) if hasattr(v, "__len__") else "-"}')
# 搜索与"上限/储备"相关的字符串
for kw in ('上限', '储备', '应急', 'MaxCost', 'maxCost'):
    if kw in s:
        i = s.index(kw)
        print(f'\n含「{kw}」片段: …{s[max(0,i-120):i+160]}')
