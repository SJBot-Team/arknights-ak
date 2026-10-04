# -*- coding: utf-8 -*-
"""临时：查令/弦惊/蕾缪安 部署费用与技能描述（读取工作区内的解包备份表）"""
import json
import sys
import os

sys.stdout.reconfigure(encoding='utf-8')
BASE = r'C:\Users\23922\Documents\ds_harness\ak\data\gamedata_akgd'

ct = json.load(open(os.path.join(BASE, 'character_table.json'), encoding='utf-8'))


def cost(cid):
    v = ct.get(cid)
    if not v:
        return None
    return v['phases'][-1]['attributesKeyFrames'][-1]['data'].get('cost')


for cid in ('char_2023_ling', 'token_10020_ling_soul1', 'token_10020_ling_soul2',
            'token_10020_ling_soul3', 'char_4193_lemuen', 'char_1029_yato2',
            'char_4091_ulika', 'char_250_phatom', 'char_4123_ela', 'token_10033_ela_grzmot'):
    v = ct.get(cid)
    print(f'{cid:<28} name={v["name"] if v else "-":<10} cost={cost(cid)}')

ling = ct['char_2023_ling']
print('\n令 skills:', ling['skills'])
print('令 talents:', [t.get('candidates', [{}])[-1].get('name') for t in ling.get('talents', [])])

st_p = os.path.join(BASE, 'skill_table.json')
if os.path.exists(st_p):
    st = json.load(open(st_p, encoding='utf-8'))
    for sid in (ling['skills'] if isinstance(ling['skills'], list) else []):
        pass
    # 找令的技能
    for k, v in st.items():
        if k.startswith('skchr_ling') or 'ling' in k.lower():
            lv = v.get('levels', [{}])[-1]
            print(f'\n[{k}] {v.get("levels",[{}])[0].get("name","")}')
            print('  desc:', (lv.get('description') or '')[:300])
else:
    print('\nskill_table.json 不存在:', st_p)
