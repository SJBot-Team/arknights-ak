# -*- coding: utf-8 -*-
"""dump 诺伯特平民 enemy_1313_wdfmr 的全部机制字段（技能/天赋/黑板）"""
import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
BASE = r'E:\__file\ak_kb\gamedata'

for fn in ('enemy_database_full.json', 'enemy_database.json'):
    p = os.path.join(BASE, fn)
    if not os.path.exists(p):
        continue
    d = json.load(open(p, encoding='utf-8'))
    e = (d.get('enemies') or {}).get('enemy_1313_wdfmr') if isinstance(d.get('enemies'), dict) else None
    if e is None and isinstance(d, dict):
        e = d.get('enemy_1313_wdfmr')
    print('=' * 20, fn, '命中' if e else '未命中')
    if not e:
        continue
    print('name:', e.get('name'))
    for lvl in (e.get('phases') or []):
        for i, lv in enumerate((lvl.get('attributesKeyFrames') or [])[:1]):
            print('  attrs:', json.dumps(lv.get('data'), ensure_ascii=False)[:200])
    print('  talents:', json.dumps(e.get('talents'), ensure_ascii=False)[:600])
    print('  skills:', json.dumps(e.get('skills'), ensure_ascii=False)[:600])
    for k in ('motion', 'rangeRadius', 'lifePointReduce', 'applyWay', 'weight', 'levelType'):
        if k in e:
            print(f'  {k}: {e[k]}')
    break

# 技能黑板（enemy_skills.json 里应有具体效果）
sp = os.path.join(BASE, 'enemy_skills.json')
if os.path.exists(sp):
    sk = json.load(open(sp, encoding='utf-8'))
    hit = {k: v for k, v in sk.items() if 'wdfmr' in k or 'civilian' in k.lower()}
    print('\nenemy_skills 中相关键:', list(hit.keys())[:6])
    for k, v in list(hit.items())[:2]:
        print(f'  [{k}] {json.dumps(v, ensure_ascii=False)[:400]}')
