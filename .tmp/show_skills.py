# -*- coding: utf-8 -*-
"""打印令/蕾缪安的技能数据（spData / duration / blackboard），用于实现技能系统"""
import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
BASE = r'C:\Users\23922\Documents\ds_harness\ak\data\gamedata_akgd'
ct = json.load(open(os.path.join(BASE, 'character_table.json'), encoding='utf-8'))
st = json.load(open(os.path.join(BASE, 'skill_table.json'), encoding='utf-8'))

for cid in ('char_2023_ling', 'char_4193_lemuen', 'token_10020_ling_soul3'):
    c = ct[cid]
    print('=' * 78)
    print(f'{cid}  {c["name"]}')
    for i, s in enumerate(c.get('skills') or []):
        sd = st.get(s['skillId'])
        if not sd:
            continue
        lv = sd['levels'][-1]
        bb = {b['key']: b.get('valueStr', b.get('value')) for b in (lv.get('blackboard') or [])}
        print(f'  [{i}] {s["skillId"]:<20} 名={lv.get("name")}  range={lv.get("rangeId")}')
        print(f'      spData={json.dumps(lv.get("spData"), ensure_ascii=False)}')
        print(f'      duration={lv.get("duration")}  blackboard={json.dumps(bb, ensure_ascii=False)}')
        print(f'      desc={(lv.get("description") or "")[:150]}')
