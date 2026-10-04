# -*- coding: utf-8 -*-
"""probe_kill_blow.py — 检查"击杀那一帧"的**原始切片**（确认致命一击是否被记录）。

背景：在 1-1 复刻中发现 `despawn/kill` 出现的帧（383 / 464）**看不到对应的伤害事件**，
而 854 那一帧却看得到（dmg=335）。需要确认是"引擎没结算"还是"事件提取漏了"。
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

from ak_sim.engine import Battle              # noqa: E402
from ak_sim.scenario import Scenario          # noqa: E402

STAGE = '1-1'
FANG, MIDN = 'char_123_fang', 'char_283_midn'
DEPLOYS = [(10, FANG, 'D6', '左', 8), (411, MIDN, 'D4', '上', None)]
WATCH = [int(v) for v in (sys.argv[1].split(',') if len(sys.argv) > 1
                          else '381,382,383,384,462,463,464,465,852,853,854,855'.split(','))]
FRAMES = max(WATCH) + 2


def to_rc(tile):
    return ord(tile[0]) - 65, int(tile[1:]) - 1


def main():
    sc = Scenario(STAGE)
    b = Battle(sc.stage_code, seed=0, record=True, record_every=1, max_frames=FRAMES)
    plan = {}
    for f, char, tile, direc, cov in DEPLOYS:
        plan.setdefault(f, []).append((char, to_rc(tile), direc, cov))
    for _ in range(FRAMES):
        b.tick()
        if b.frame in plan:
            for char, (r, c), direc, cov in plan[b.frame]:
                b.deploy(char, r, c, direction={'左': '左', '上': '上'}[direc],
                         elite=2, level=90, potential=6, trust=200,
                         skill_index=0, skill_level=7, cost=cov)

    for fr in WATCH:
        slot = next((s for s in b.frames if s.get('f') == fr), None)
        if slot is None:
            print(f'帧 {fr}: 无切片')
            continue
        ops = slot.get('ops') or []
        print(f'--- 帧 {fr}  ops={len(ops)}')
        for o in ops:
            print('    ', json.dumps(o, ensure_ascii=False, default=str))
        for k in ('enemies', 'units', 'ally'):
            if k in slot:
                v = slot[k]
                if isinstance(v, list) and v:
                    print(f'     {k}: ' + json.dumps(v, ensure_ascii=False, default=str)[:600])


if __name__ == '__main__':
    main()
