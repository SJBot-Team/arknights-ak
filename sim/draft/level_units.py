# -*- coding: utf-8 -*-
"""level_units.py — 关卡关联单位的**完整机制提取**（用户 2026-09-14 要求）

原则：**读到关卡关联到某单位时，就一次性把它的全部信息与关联机制取出来**，而不是用到才现查。
覆盖三类来源：
  1. `predefines.tokenInsts / characterInsts`（预置干员/装置，如「街头应急储备」trap_111_wdfarm）
  2. `enemyDbRefs`（关卡敌人实例，含 level 与 overwrittenData 覆盖字段）
  3. `runes / globalBuffs`（关卡词条：费用上限、敌人属性乘区、附加能力…）

对每个单位输出：名称 / 职业 / 关键属性 / **天赋黑板（on-death 等机制）** / 技能表 / 与关卡机制的关联。
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

BASE = r'E:\__file\ak_kb\gamedata'
CT = json.load(open(os.path.join(BASE, 'character_table.json'), encoding='utf-8'))
HB = json.load(open(os.path.join(BASE, 'enemy_handbook_table.json'), encoding='utf-8'))
ESK = json.load(open(os.path.join(BASE, 'enemy_skills.json'), encoding='utf-8')) \
    if os.path.exists(os.path.join(BASE, 'enemy_skills.json')) else {}


def talent_bb(spec: dict) -> dict:
    out = {}
    for t in (spec.get('talents') or []):
        for cand in (t.get('candidates') or []):
            for b in (cand.get('blackboard') or []):
                v = b.get('valueStr')
                out[b['key']] = v if v is not None else b.get('value')
    return out


def report(level_path: str):
    d = json.load(open(level_path, encoding='utf-8'))
    print(f'=== 关卡 {os.path.basename(level_path)} ===')
    print('runes:')
    for r in (d.get('runes') or []):
        bb = {b.get('key'): (b.get('valueStr') if b.get('valueStr') is not None else b.get('value'))
              for b in (r.get('blackboard') or [])}
        print(f'  - {r.get("key")}: {json.dumps(bb, ensure_ascii=False)}')

    print('\n预置单位（predefines）:')
    for kind in ('characterInsts', 'tokenInsts'):
        for inst in ((d.get('predefines') or {}).get(kind) or []):
            key = (inst.get('inst') or {}).get('characterKey')
            pos = inst.get('position') or {}
            c = CT.get(key) or {}
            bb = talent_bb(c)
            name = c.get('name')
            hp = None
            try:
                hp = c['phases'][-1]['attributesKeyFrames'][-1]['data'].get('maxHp')
            except Exception:
                pass
            print(f'  - [{kind}] {key} 「{name}」 @(r{pos.get("row")},c{pos.get("col")}) '
                  f'HP={hp} 天赋黑板={json.dumps(bb, ensure_ascii=False)}')
            for sk in (c.get('skills') or []):
                print(f'      技能 {sk.get("skillId")}')

    print('\n关卡敌人实例（enemyDbRefs）:')
    for r in (d.get('enemyDbRefs') or []):
        eid = r['id']
        nm = ((HB.get('enemyData') or {}).get(eid) or {}).get('name') or eid
        lvl = r.get('level')
        od = r.get('overwrittenData')
        defined = []
        if isinstance(od, dict):
            for k, v in od.items():
                if isinstance(v, dict) and v.get('m_defined'):
                    defined.append(k)
        flag = ''
        if 'wdfmr' in eid:
            sk = ESK.get('wdfmr_cost') or {}
            flag = (' ← 平民机制：' + json.dumps(sk.get('tooltip', {}).get('zh'), ensure_ascii=False)
                    if sk else ' ← 平民（无技能数据）')
        print(f'  - {eid:<26} {nm:<10} level={lvl} 覆盖={defined or "-"}{flag}')


if __name__ == '__main__':
    p = sys.argv[1] if len(sys.argv) > 1 else \
        r'E:\__file\ak_kb\gamedata\levels\obt\hard\level_hard_12-04.json'
    report(p)
