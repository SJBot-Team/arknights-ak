# -*- coding: utf-8 -*-
"""打印技能真实 blackboard 数值（修正 valueStr=None 的取值）"""
import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
BASE = r'C:\Users\23922\Documents\ds_harness\ak\data\gamedata_akgd'
ct = json.load(open(os.path.join(BASE, 'character_table.json'), encoding='utf-8'))
st = json.load(open(os.path.join(BASE, 'skill_table.json'), encoding='utf-8'))


def bb_of(lv):
    out = {}
    for b in (lv.get('blackboard') or []):
        v = b.get('valueStr')
        out[b['key']] = v if v is not None else b.get('value')
    return out


for cid in ('char_2023_ling', 'char_4193_lemuen'):
    c = ct[cid]
    print('=' * 70)
    print(cid, c['name'])
    for i, s in enumerate(c.get('skills') or []):
        sd = st.get(s['skillId'])
        lv = sd['levels'][-1]
        print(f'  [{i}] {lv.get("name")} sp={json.dumps(lv.get("spData"), ensure_ascii=False)} '
              f'duration={lv.get("duration")}')
        print(f'      bb={json.dumps(bb_of(lv), ensure_ascii=False)}')

# 模组数据（令 uniequip_002_ling / 蕾缪安 uniequip_002_lemuen）
try:
    bet = json.load(open(os.path.join(BASE, 'battle_equip_table.json'), encoding='utf-8'))
    for mid in ('uniequip_002_ling', 'uniequip_002_lemuen'):
        me = bet.get(mid)
        if not me:
            print(f'  {mid}: 表中不存在')
            continue
        ph = (me.get('phases') or [])[-1]
        print('=' * 70)
        print(mid, me.get('name'))
        print('  attributeBlackboard:', json.dumps(ph.get('attributeBlackboard'), ensure_ascii=False))
        print('  talentBlackboard:', json.dumps(ph.get('talentBlackboard'), ensure_ascii=False)[:400])
except FileNotFoundError:
    print('battle_equip_table.json 不存在')
