# -*- coding: utf-8 -*-
"""找「平民」类单位并 dump 其全部机制字段（技能/天赋黑板）——回答"仅上限 还是 附带回费" """
import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
BASE = r'E:\__file\ak_kb\gamedata'
print('数据目录文件:', [f for f in os.listdir(BASE) if 'enem' in f.lower() or 'handbook' in f.lower()][:10])

# 1) 从敌人表找名字含「平民」的 key
cands = []
for fn in ('enemy_database.json', 'enemy_handbook_table.json', 'enemy_table.json'):
    p = os.path.join(BASE, fn)
    if not os.path.exists(p):
        continue
    d = json.load(open(p, encoding='utf-8'))
    def walk(obj, path=''):
        if isinstance(obj, dict):
            nm = obj.get('name')
            if isinstance(nm, str) and '平民' in nm:
                cands.append((fn, path, nm, obj))
            for k, v in obj.items():
                walk(v, f'{path}/{k}')
        elif isinstance(obj, list):
            for i, v in enumerate(obj[:200]):
                walk(v, f'{path}[{i}]')
    walk(d)
    if cands:
        break

print(f'\n含「平民」的条目 {len(cands)} 个：')
for fn, path, nm, obj in cands[:3]:
    print(f'  [{fn}] {path} name={nm}')
    for k in ('key', 'id', 'enemyId', 'skills', 'talents', 'description'):
        if k in obj:
            print(f'     {k}: {json.dumps(obj[k], ensure_ascii=False)[:300]}')
    ab = obj.get('attributes') or {}
    if ab:
        print('     attributes:', json.dumps(ab, ensure_ascii=False)[:200])
