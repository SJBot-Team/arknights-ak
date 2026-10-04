# -*- coding: utf-8 -*-
"""replay_verify2.py — ★改用"按序号对齐"的事件配对（比"最近帧匹配"稳健）

## 为什么要改
本关两只敌人都叫「猎狗pro」（内部 key: `enemy_1000_gopro` / `_2`），
而标定表用「猎狗pro 1 / 猎狗pro 2」区分 ⇒ 按"名字包含"匹配会把两者事件混在一起，
导致"芬第 n 次命中"错配到别的实例上（表现为间隔不均、偏差 ±15~17）。

## 配对规则（按序号对齐）
1. 把**标定事件**按 `(受害者阵营, 事件类别)` 分组，组内按帧升序编号；
2. 把**模拟器事件**按同样规则分组、编号；
3. **组内第 n 个配第 n 个**（而非"全局最近帧"）；
4. 组内数量不等时，多出的按"最近帧"兜底并标注数量差。

受害者阵营：标定的"单位"列若是我方干员名（芬/月见夜）⇒ ALLY，否则 ⇒ ENEMY；
模拟器事件的 `name` 同理。
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

from ak_sim.engine import Battle              # noqa: E402
from ak_sim.events import extract_events      # noqa: E402
from ak_sim.scenario import Scenario          # noqa: E402

STAGE = '1-1'
FANG, MIDN = 'char_123_fang', 'char_283_midn'
ALLY_NAMES = ('芬', '月见夜', '令', '蕾缪安')
DIR_MAP = {'左': '左', '右': '右', '上': '上', '下': '下'}
DEPLOYS = [(10, FANG, 'D6', '左', 8), (411, MIDN, 'D4', '上', None)]

CALIB = [
    (94, '猎狗pro 1', '出现影子'), (207, '芬', '进入攻击前摇'), (221, '猎狗pro 1', '芬 命中'),
    (236, '猎狗pro 1', '芬 阻挡'), (253, '猎狗pro 1', '芬命中'), (255, '芬', '猎狗pro 1 命中'),
    (285, '猎狗pro 1', '芬 命中'), (298, '芬', '猎狗pro 1 命中'), (317, '猎狗pro 1', '芬 命中'),
    (340, '芬', '猎狗pro 1 命中'), (349, '猎狗pro 1', '芬 命中'), (367, '猎狗pro 2', '出现影子'),
    (381, '猎狗pro 1', '芬 击杀'), (432, '猎狗pro 2', '芬 命中'),
    (438, '猎狗pro 2', '月见夜 远程命中'), (443, '猎狗pro 2', '芬 阻挡'),
    (461, '芬', '猎狗pro 2 命中'), (464, '猎狗pro 2', '芬 击杀'),
]
KIND_MAP = {'出现影子': ('spawn',), '进入攻击前摇': ('damage_first', 'damage'),
            '命中': ('damage', 'damage_first'), '阻挡': ('damage', 'damage_first', 'spawn'),
            '击杀': ('despawn', 'damage', 'damage_first')}


def classify(desc):
    for k, v in KIND_MAP.items():
        if k in desc:
            return k, v
    return '?', ()


def camp(name: str):
    n = str(name or '')
    return 'ALLY' if any(a in n for a in ALLY_NAMES) else 'ENEMY'


def to_rc(tile):
    return ord(tile[0]) - 65, int(tile[1:]) - 1


def main():
    sc = Scenario(STAGE)
    b = Battle(sc.stage_code, seed=0, record=True, record_every=1, max_frames=700)
    plan = {}
    for f, char, tile, direc, cov in DEPLOYS:
        plan.setdefault(f, []).append((char, to_rc(tile), direc, cov))
    for f in range(700):
        b.tick()
        if b.frame in plan:
            for char, (r, c), direc, cov in plan[b.frame]:
                b.deploy(char, r, c, direction=DIR_MAP[direc], elite=2, level=90,
                         potential=6, trust=200, skill_index=0, skill_level=7, cost=cov)

    ev = extract_events(b.frames)
    # 模拟器事件：按 (类别, 阵营) 分组
    sim_groups = {}
    for e in ev:
        t = e['type']
        cat = ('出现影子' if t == 'spawn' else
               '击杀' if t in ('despawn', 'kill') else
               '命中')                      # damage / damage_first 一律归入"命中"组
        sim_groups.setdefault((cat, camp(e.get('name'))), []).append(e['frame'])
    for k in sim_groups:
        sim_groups[k].sort()

    # 标定事件：按 (类别, 阵营) 分组
    cal_groups = {}
    for f, unit, desc in CALIB:
        cat, _ = classify(desc)
        # "进入攻击前摇/阻挡"也归入"命中"组的首/次位（避免与命中抢编号）
        gcat = '出现影子' if cat == '出现影子' else ('击杀' if cat == '击杀' else '命中')
        cal_groups.setdefault((gcat, camp(unit)), []).append((f, unit, desc))
    for k in cal_groups:
        cal_groups[k].sort(key=lambda z: z[0])

    print(f'{"标定帧":>6} {"受害者":>10} {"阵营":>6} {"动画层":>16} {"组内#":>5} '
          f'{"模拟器帧":>9} {"偏差":>6}')
    print('-' * 76)
    diffs, used = [], {}
    for (gcat, gcamp), items in sorted(cal_groups.items(), key=lambda kv: kv[1][0][0]):
        sims = sim_groups.get((gcat, gcamp), [])
        for i, (f, unit, desc) in enumerate(items):
            if i < len(sims):
                ef = sims[i]
                d = abs(ef - f)
                diffs.append(d)
                print(f'{f:>6} {unit:>10} {gcamp:>6} {desc:>16} {i:>5} {ef:>9} {ef - f:>+6}'
                      + ('  OK' if d <= 6 else '  ★偏大'))
            else:
                print(f'{f:>6} {unit:>10} {gcamp:>6} {desc:>16} {i:>5} {"(缺)":>9} {"-":>6}')
    print('-' * 76)
    if diffs:
        hit = sum(1 for d in diffs if d <= 6)
        print(f'可对齐 {len(diffs)}/{len(CALIB)}；|偏差|≤6 帧 {hit} 条；'
              f'平均 {sum(diffs)/len(diffs):.2f} 帧；最大 {max(diffs)} 帧')
        print('偏差分布: ' + ', '.join(str(d) for d in sorted(diffs)))
    print('\n各组事件数对照（标定 vs 模拟器）:')
    for k in sorted(set(list(cal_groups.keys()) + list(sim_groups.keys())), key=str):
        print(f'  {k}: 标定 {len(cal_groups.get(k, []))} vs 模拟 {len(sim_groups.get(k, []))}')


if __name__ == '__main__':
    main()
