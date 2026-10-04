# -*- coding: utf-8 -*-
"""查 h12-4 里「应急储备」「平民」两类单位的**全部关联机制**

用户更正（2026-09-14）：
  1) 应急储备**不会被敌人攻击**，但会**影响敌人寻路**；
  2) **我方单位可以攻击它**并获取费用；
  3) 另有**平民**：被查明身份后进入目标点 → 提升上限。
     需辨明：**仅提升上限 还是 附带费用回复**。
"""
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
BASE = r'E:\__file\ak_kb\gamedata'
LV = os.path.join(BASE, 'levels', 'obt', 'hard', 'level_hard_12-04.json')
d = json.load(open(LV, encoding='utf-8'))
ct = json.load(open(os.path.join(BASE, 'character_table.json'), encoding='utf-8'))
et = json.load(open(os.path.join(BASE, 'enemy_handbook_table.json'), encoding='utf-8')) \
    if os.path.exists(os.path.join(BASE, 'enemy_handbook_table.json')) else {}

print('=== 关卡内所有 enemyDbRefs（含 level / overwrittenData 是否定义）===')
for r in (d.get('enemyDbRefs') or []):
    od = r.get('overwrittenData')
    defined = []
    if od:
        for k, v in od.items():
            if isinstance(v, dict) and v.get('m_defined'):
                defined.append(f'{k}={v.get("m_value")}')
            elif isinstance(v, dict) and isinstance(v.get('attributes'), dict):
                for k2, v2 in v['attributes'].items():
                    if isinstance(v2, dict) and v2.get('m_defined'):
                        defined.append(f'{k}.{k2}={v2.get("m_value")}')
    nm = ct.get(r['id'], {}).get('name') or et.get(r['id'], {}).get('name')
    print(f'  {r["id"]:<26} level={r.get("level")} name={nm} 覆盖字段={defined or "-"}')

print('\n=== 关卡内名字含「平民」的单位 ===')
for r in (d.get('enemyDbRefs') or []):
    nm = (ct.get(r['id'], {}) or {}).get('name') or ''
    if '平民' in nm:
        print(' ', json.dumps(r, ensure_ascii=False)[:400])

print('\n=== runes / globalBuffs 全文（找 平民/上限/费用 相关键）===')
for r in (d.get('runes') or []):
    print('  rune:', json.dumps(r, ensure_ascii=False)[:300])
for b in (d.get('globalBuffs') or []):
    print('  gbuff:', json.dumps(b, ensure_ascii=False)[:300])

s = json.dumps(d, ensure_ascii=False)
for kw in ('civilian', 'Civilian', '平民', 'identify', 'Identify', '查明', 'wdfarm'):
    idxs = [m.start() for m in re.finditer(kw, s)][:2]
    for i in idxs:
        print(f'\n[{kw}] …{s[max(0,i-160):i+200]}')
