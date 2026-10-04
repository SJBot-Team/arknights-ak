# -*- coding: utf-8 -*-
"""sweep_windup.py — 扫描"攻击前摇比例"参数，找使事件偏差最小的组合

## 背景
- 干员侧前摇比例 0.4375（由标定反推 14/32）使平均偏差 14.50 → 9.06；
- 敌人侧也加 0.4375 后平均偏差反而升到 12.11，但部分事件改善 ⇒ **敌人比例与干员不同**；
⇒ 本脚本对 **干员比例 × 敌人比例** 做二维扫描，用 `replay_verify` 的"平均|偏差|"作为目标函数。

## 判分
对 18 条标定事件，计算"标定帧 − 模拟器最近同类事件帧"的 |偏差| 平均值与最大值。
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
CALIB = [
    (94, '出现影子'), (207, '进入攻击前摇'), (221, '芬 命中'), (236, '芬 阻挡'),
    (253, '芬命中'), (255, '猎狗pro 1 命中'), (285, '芬 命中'), (298, '猎狗pro 1 命中'),
    (317, '芬 命中'), (340, '猎狗pro 1 命中'), (349, '芬 命中'), (367, '出现影子'),
    (381, '芬 击杀'), (432, '芬 命中'), (438, '月见夜 远程命中'), (443, '芬 阻挡'),
    (461, '猎狗pro 2 命中'), (464, '芬 击杀'),
]
KIND_MAP = {'出现影子': ('spawn',), '进入攻击前摇': ('damage_first', 'damage'),
            '命中': ('damage',), '阻挡': ('damage', 'spawn'), '击杀': ('despawn', 'damage')}


def classify(desc):
    for k, v in KIND_MAP.items():
        if k in desc:
            return v
    return ()


def run(op_ratio: float, en_ratio: float):
    sc = Scenario(STAGE)
    b = Battle(sc.stage_code, seed=0, record=True, record_every=1, max_frames=700)
    plan = {}
    for f, char, tile, direc, cov in DEPLOYS:
        plan.setdefault(f, []).append((char, (ord(tile[0]) - 65, int(tile[1:]) - 1), direc, cov))
    for f in range(700):
        b.tick()
        if b.frame in plan:
            for char, (r, c), direc, cov in plan[b.frame]:
                u = b.deploy(char, r, c, direction=DIR_MAP[direc], elite=2, level=90,
                             potential=6, trust=200, skill_index=0, skill_level=7, cost=cov)
                if u is not None:
                    try:
                        u._windup_ratio = op_ratio
                    except Exception:
                        pass
        # 敌人侧比例：每帧给所有敌人设置（新生成的也会在下一帧被设上）
        for un in b.units.values():
            if un.side != 'ALLY':
                try:
                    un._windup_ratio = en_ratio
                except Exception:
                    pass
    ev = extract_events(b.frames)
    kinds = {}
    for e in ev:
        kinds.setdefault(e['type'], []).append(e['frame'])
    diffs = []
    for f, desc in CALIB:
        cands = []
        for t in classify(desc):
            for ef in kinds.get(t, []):
                cands.append(abs(ef - f))
        if cands:
            diffs.append(min(cands))
    if not diffs:
        return None
    return sum(diffs) / len(diffs), max(diffs), len(diffs)


def main():
    print('干员比例 × 敌人比例 扫描（目标：平均|偏差| 最小）')
    print(f'{"干员":>7} {"敌人":>7} {"平均偏差":>9} {"最大":>6} {"条数":>5}')
    best = None
    for op_r in (0.0, 0.2188, 0.4375, 0.5):
        for en_r in (0.0, 0.1, 0.2188, 0.4375, 0.5):
            r = run(op_r, en_r)
            if not r:
                print(f'{op_r:>7} {en_r:>7}   （无数据）')
                continue
            avg, mx, n = r
            mark = ''
            if best is None or avg < best[0]:
                best = (avg, op_r, en_r, mx)
                mark = '  ← 目前最优'
            print(f'{op_r:>7} {en_r:>7} {avg:>9.2f} {mx:>6} {n:>5}{mark}')
    if best:
        print(f'\n⇒ 最优：干员比例={best[1]}、敌人比例={best[2]}，平均偏差={best[0]:.2f} 帧，最大={best[3]} 帧')
        print('  （基线：双 0 时平均 14.50；仅干员 0.4375 时平均 9.06）')


if __name__ == '__main__':
    main()
