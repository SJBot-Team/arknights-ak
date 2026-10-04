# -*- coding: utf-8 -*-
"""sweep_enemy_windup.py — 扫描"敌侧前摇比例"以收敛"猎狗pro 打芬"的相位偏差

## 现状（上一轮）
复刻与标定的 15 条已对齐、平均 3.13 帧、最大 8 帧；残余集中在：
- **帧255/298/340「猎狗pro 命中 芬」−8 / −8 / −7**（敌方打我的相位，间隔 42~43 与实机一致，仅相位偏）；
- 帧367「猎狗 出现影子」−7；
- 帧461「猎狗 命中 芬」缺。

⇒ 本脚本扫描**敌侧前摇比例**（当前 `WINDUP_RATIO_DEFAULT_ENEMY = 0.10`），
观察"敌打芬"三条的偏差是否收敛，同时监控"芬打敌"五条是否受影响。

判分：所有可对齐事件的**平均|偏差|**（主）+ 最大|偏差|（辅）。
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
DIR_MAP = {'左': '左', '上': '上'}
DEPLOYS = [(10, FANG, 'D6', '左', 8), (411, MIDN, 'D4', '上', None)]

MAP = [
    (94,  'spawn', '猎狗pro', '-',      0),
    (207, 'dmg',   '芬',      '猎狗pro', 0),
    (221, 'dmg',   '猎狗pro', '芬',      0),
    (253, 'dmg',   '猎狗pro', '芬',      1),
    (255, 'dmg',   '芬',      '猎狗pro', 1),
    (285, 'dmg',   '猎狗pro', '芬',      2),
    (298, 'dmg',   '芬',      '猎狗pro', 2),
    (317, 'dmg',   '猎狗pro', '芬',      3),
    (340, 'dmg',   '芬',      '猎狗pro', 3),
    (349, 'dmg',   '猎狗pro', '芬',      4),
    (367, 'spawn', '猎狗',    '-',      0),
    (381, 'kill',  '猎狗pro', '-',      0),
    (432, 'dmg',   '猎狗',    '芬',      0),
    (438, 'dmg',   '猎狗',    '月见夜',  0),
    (461, 'dmg',   '芬',      '猎狗',    2),
    (464, 'kill',  '猎狗',    '-',      0),
]


def to_rc(tile):
    return ord(tile[0]) - 65, int(tile[1:]) - 1


def run(en_ratio: float):
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
        for un in b.units.values():
            if un.side != 'ALLY':
                un._windup_ratio = en_ratio
    ev = extract_events(b.frames)
    idx = {}
    for e in ev:
        t, uid = e['type'], e.get('uid')
        nm = str(e.get('name') or '')
        if t == 'spawn':
            idx.setdefault(('spawn', nm, '-'), []).append(e['frame'])
        elif t in ('damage', 'damage_first'):
            idx.setdefault(('dmg', nm, str(e.get('src') or '-')), []).append(e['frame'])
        elif t in ('despawn', 'kill'):
            idx.setdefault(('kill', nm, '-'), []).append(e['frame'])
    for k in idx:
        idx[k] = sorted(set(idx[k]))
    diffs, detail = [], []
    for f, cat, vic, atk, i in MAP:
        key = (cat, vic, atk) if cat == 'dmg' else (cat, vic, '-')
        fr = idx.get(key, [])
        if i < len(fr):
            d = abs(fr[i] - f)
            diffs.append(d)
            detail.append((f, fr[i], fr[i] - f))
        else:
            detail.append((f, None, None))
    if not diffs:
        return None
    return sum(diffs) / len(diffs), max(diffs), len(diffs), detail


def main():
    print('扫描敌侧前摇比例（干员侧固定 0.55）')
    print(f'{"敌比例":>8} {"平均":>7} {"最大":>5} {"条数":>5}')
    best = None
    for r in (0.0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40):
        res = run(r)
        if not res:
            continue
        avg, mx, n, detail = res
        mark = ''
        if best is None or avg < best[0]:
            best = (avg, r, mx, detail)
            mark = '  ← 最优'
        print(f'{r:>8} {avg:>7.2f} {mx:>5} {n:>5}{mark}')
    if best:
        print(f'\n⇒ 最优敌比例 = {best[1]}，平均 {best[0]:.2f}，最大 {best[2]}')
        print('  逐条（标定帧, 模拟器帧, 偏差）:')
        for f, ef, d in best[3]:
            print(f'    {f:>4} → {str(ef):>5}  {str(d):>5}')


if __name__ == '__main__':
    main()
