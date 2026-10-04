# -*- coding: utf-8 -*-
"""查 trap_111_wdfarm（街头应急储备？）的属性与效果"""
import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
BASE = r'E:\__file\ak_kb\gamedata'
ct = json.load(open(os.path.join(BASE, 'character_table.json'), encoding='utf-8'))
key = 'trap_111_wdfarm'
c = ct.get(key)
if not c:
    cands = [k for k in ct if k.startswith('trap_111') or 'wdfarm' in k]
    print('未找到，候选:', cands[:10])
    key = cands[0] if cands else None
    c = ct.get(key) if key else None
if c:
    print('key:', key, '| name:', c.get('name'), '| profession:', c.get('profession'))
    ph = (c.get('phases') or [])[-1]
    a = (ph.get('attributesKeyFrames') or [{}])[-1].get('data') or {}
    print('hp:', a.get('maxHp'), 'atk:', a.get('atk'), 'def:', a.get('def'), 'block:', a.get('blockCnt'))
    print('talents:', json.dumps(c.get('talents'), ensure_ascii=False)[:500])
    print('trait:', json.dumps(c.get('trait'), ensure_ascii=False)[:300])
    print('skills:', json.dumps(c.get('skills'), ensure_ascii=False)[:300])
    print('desc:', (c.get('description') or '')[:200])
# 全局 buff / 关卡 buff 里找费用上限相关
LV = os.path.join(BASE, 'levels', 'obt', 'hard', 'level_hard_12-04.json')
d = json.load(open(LV, encoding='utf-8'))
print('\nglobalBuffs:', json.dumps(d.get('globalBuffs'), ensure_ascii=False)[:300])
print('optionalRunes:', json.dumps(d.get('optionalRunes'), ensure_ascii=False)[:300])
