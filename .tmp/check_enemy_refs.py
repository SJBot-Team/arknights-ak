# -*- coding: utf-8 -*-
"""查看 h12-4 的 enemyDbRefs.overwrittenData 与 enemy_attribute_mul rune 的结构"""
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')
F = r'E:\__file\ak_kb\gamedata\levels\obt\hard\level_hard_12-04.json'
d = json.load(open(F, encoding='utf-8'))

print('=== runes 全量 ===')
for r in (d.get('runes') or []):
    bb = {b.get('key'): (b.get('valueStr') if b.get('valueStr') is not None else b.get('value'))
          for b in (r.get('blackboard') or [])}
    print(f'  key={r.get("key")}  bb={json.dumps(bb, ensure_ascii=False)}')

print('\n=== enemyDbRefs 前 3 条 ===')
for r in (d.get('enemyDbRefs') or [])[:3]:
    print(' ', json.dumps(r, ensure_ascii=False)[:520])

print('\n=== enemies（波次里引用）前 2 条 ===')
for r in (d.get('enemies') or [])[:2]:
    print(' ', json.dumps(r, ensure_ascii=False)[:300])
