# -*- coding: utf-8 -*-
"""生成「模组与天赋覆写」批量表 → ak\\glossary\\09_模组与天赋.tsv。

为什么需要：`uniequip_table.json` 的 `uniEquipName` 与 `battle_equip_table.json` 里的**天赋覆写名**
（例：煌的模组「稍后回来」的天赋覆写名 **紧急除颤**）此前**不在任何批量表里** ⇒ 查词查不到。
本脚本独立于 `glossary_build.py`（后者由他人维护），可单独重跑。

列（主 schema 7 列 + 附加）：拼音 | 官方汉语命名 | 代码层ID | 一句话说明 | 知识库地址 | 玩家俗称 | 来源 | 干员 | 类型 | 阶段
"""
import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
A = r'C:\Users\23922\Documents\ds_harness\ak'
G = os.path.join(A, 'glossary')
GD = os.path.join(A, 'data', 'gamedata_akgd')
OUT = os.path.join(G, '09_模组与天赋.tsv')
HEADER = ['汉语拼音', '官方汉语命名', '代码层ID', '一句话说明', '知识库地址', '玩家俗称', '来源', '干员/单位', '类型', '阶段/等级']


def main():
    uni = json.load(open(os.path.join(GD, 'uniequip_table.json'), encoding='utf-8'))
    eq = uni.get('equipDict', {})
    rows = []
    src = 'gamedata uniequip_table.json · equipDict'
    for eid, v in sorted(eq.items()):
        if not isinstance(v, dict):
            continue
        name = v.get('uniEquipName') or ''
        if not name:
            continue
        rows.append(['', name, eid, '', '', '', src,
                     v.get('charId') or '', (v.get('typeName1') or '') + (('/' + v['typeName2']) if v.get('typeName2') else ''),
                     v.get('typeName2') or ''])
    # 天赋覆写名（battle_equip_table：这些名字是"天赋名"，如「紧急除颤」）
    try:
        be = json.load(open(os.path.join(GD, 'battle_equip_table.json'), encoding='utf-8'))
    except Exception:
        be = {}
    seen = {(r[2], r[1]) for r in rows}
    src2 = 'gamedata battle_equip_table.json · addOrOverrideTalentDataBundle'
    def walk(o, owner=''):
        if isinstance(o, dict):
            if o.get('name') and isinstance(o.get('name'), str):
                # ⚠️ 主键唯一：天赋覆写名与模组共用同一个 uniequipId，必须用 `id@名字` 形式区分，
                #    否则同一 ID 会出现多行（doctor 的主键唯一性检查会报错）。
                key = (f'{owner}@{o["name"]}', o['name'])
                if key not in seen:
                    seen.add(key)
                    rows.append(['', o['name'], key[0], '', '', '', src2, '', '天赋覆写', ''])
            for k, v in o.items():
                walk(v, owner)
        elif isinstance(o, list):
            for v in o:
                walk(v, owner)
    for kid, kv in (be.items() if isinstance(be, dict) else []):
        walk(kv, kid)
    with open(OUT, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\t'.join(HEADER) + '\n')
        for r in rows:
            f.write('\t'.join(str(c).replace('\t', ' ') for c in r) + '\n')
    print(f'写出 {os.path.basename(OUT)}: {len(rows)} 行')
    for r in rows[:5]:
        print('  ', r[2], '|', r[1], '|', r[7])
    hit = [r for r in rows if r[1] == '紧急除颤']
    print('「紧急除颤」命中:', len(hit))
    for r in hit[:4]:
        print('   ', r[2], r[7], r[8])
    return 0


if __name__ == '__main__':
    sys.exit(main())
