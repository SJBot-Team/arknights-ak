# -*- coding: utf-8 -*-
"""打印令/蕾缪安的天赋（找是否有 SP 相关效果），用于核对 SP 节奏"""
import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
BASE = r'C:\Users\23922\Documents\ds_harness\ak\data\gamedata_akgd'
ct = json.load(open(os.path.join(BASE, 'character_table.json'), encoding='utf-8'))
tal = json.load(open(os.path.join(BASE, 'talent_table.json'), encoding='utf-8')) \
    if os.path.exists(os.path.join(BASE, 'talent_table.json')) else {}

for cid in ('char_2023_ling', 'char_4193_lemuen'):
    c = ct[cid]
    print('=' * 70)
    print(cid, c['name'])
    for t in (c.get('talents') or []):
        for cand in (t.get('candidates') or []):
            print(f'  [{cand.get("unlockCondition", {}).get("phase")}] {cand.get("name")}')
            print(f'      {cand.get("description")}')
            if cand.get('blackboard'):
                print(f'      bb={json.dumps(cand["blackboard"], ensure_ascii=False)}')
