# -*- coding: utf-8 -*-
"""生成「职业与分支」批量表 → ak\\glossary\\07_职业与分支.tsv（官方分支中文名 ↔ subProfessionId）。

数据源：`ak\\data\\gamedata_akgd\\uniequip_table.json` 的 `subProfDict`（官方分支名）与 `subProfToProfDict`（分支→职业）。
干员数来自 `character_table.json` 的 `subProfessionId` 统计。
本脚本独立于 `glossary_build.py`（后者由另一路在改），可单独重跑。
"""
import json
import os
import sys
import collections

sys.stdout.reconfigure(encoding='utf-8')
A = r'C:\Users\23922\Documents\ds_harness\ak'
G = os.path.join(A, 'glossary')
GD = os.path.join(A, 'data', 'gamedata_akgd')
OUT = os.path.join(G, '07_职业与分支.tsv')
HEADER = ['汉语拼音', '官方汉语命名', '代码层ID', '一句话说明', '知识库地址', '玩家俗称', '来源',
          '所属职业', '分类', '干员/单位数']
PROF_ZH = {'PIONEER': '先锋', 'WARRIOR': '近卫', 'SNIPER': '狙击', 'TANK': '重装',
           'MEDIC': '医疗', 'CASTER': '术师', 'SUPPORT': '辅助', 'SPECIAL': '特种'}


def main():
    uni = json.load(open(os.path.join(GD, 'uniequip_table.json'), encoding='utf-8'))
    char = json.load(open(os.path.join(GD, 'character_table.json'), encoding='utf-8'))
    sub = uni.get('subProfDict', {})

    # 分支 → 职业：直接用 character_table 里「同一 subProfessionId 出现的 profession」投票得出
    # （`subProfToProfDict` 存的是位掩码 512/1 之类，不是职业枚举，不可直接用）
    pair = collections.Counter()
    for v in char.values():
        if isinstance(v, dict) and v.get('subProfessionId') and v.get('profession'):
            pair[(v['subProfessionId'], v['profession'])] += 1
    prof_of_branch = {}
    for (sid, prof), c in pair.most_common():
        prof_of_branch.setdefault(sid, prof)

    def prof_of(sid):
        return prof_of_branch.get(sid, '')

    cnt = collections.Counter(v.get('subProfessionId') for v in char.values() if isinstance(v, dict))
    rows = []
    for sid, v in sorted(sub.items(), key=lambda kv: (prof_of(kv[0]), -cnt.get(kv[0], 0))):
        name = v.get('subProfessionName') or ''
        prof = prof_of(sid)
        src = 'gamedata uniequip_table.json · subProfDict'
        rows.append(['', name, sid, '', '', '', src, PROF_ZH.get(prof, prof), v.get('subProfessionCatagory', ''), cnt.get(sid, 0)])
    with open(OUT, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\t'.join(HEADER) + '\n')
        for r in rows:
            f.write('\t'.join(str(c).replace('\t', ' ') for c in r) + '\n')
    print(f'写出 {os.path.basename(OUT)}: {len(rows)} 行')
    for r in rows[:12]:
        print(f'  {r[7]:4} {r[1]:10} ({r[2]}) 单位数={r[9]}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
