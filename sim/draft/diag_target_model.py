# -*- coding: utf-8 -*-
"""diag_target_model.py — 对比「新语义（方格范围 ∪ 受击圆∩范围格）」与「旧口径（中心距≤N）」
在 1-1 复刻上的**逐条事件差异**，并对关键帧打印几何量。

用法：
    python diag_target_model.py [--hr 0.1] [--tol 1.5]
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

from ak_sim.engine import Battle              # noqa: E402
from ak_sim.scenario import Scenario          # noqa: E402
from replay_verify5 import DEPLOYS, DIR_MAP, to_rc   # noqa: E402


def run(options, frames=700):
    sc = Scenario('1-1')
    b = Battle(sc.stage_code, seed=0, record=True, record_every=1, max_frames=frames,
               options=options)
    plan = {}
    for f, char, tile, direc, cov in DEPLOYS:
        plan.setdefault(f, []).append((char, to_rc(tile), direc, cov))
    for _ in range(frames):
        b.tick()
        if b.frame in plan:
            for char, (r, c), direc, cov in plan[b.frame]:
                b.deploy(char, r, c, direction=DIR_MAP[direc], elite=2, level=90,
                         potential=6, trust=200, skill_index=0, skill_level=7, cost=cov)
    return b


def hits(b):
    out = []
    for l in b.logs:
        if l.kind == 'hit':
            out.append((l.frame, l.detail['src'], l.detail['tgt']))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--hr', type=float, default=0.1)
    ap.add_argument('--tol', type=float, default=1.5)
    a = ap.parse_args()

    b_new = run({'hit_volume_enemy': a.hr})
    b_old = run({'range_distance_tol': a.tol})
    hn, ho = hits(b_new), hits(b_old)
    print(f'新语义 hr={a.hr}：命中 {len(hn)} 次')
    print(f'旧口径 tol={a.tol}：命中 {len(ho)} 次')
    print('\n★首次出现差异的位置：')
    for i in range(max(len(hn), len(ho))):
        x = hn[i] if i < len(hn) else None
        y = ho[i] if i < len(ho) else None
        if x != y:
            print(f'  #{i}: 新 {x}   旧 {y}')
            if i > 30:
                break

    print('\n★新语义下「靠受击体积」索敌成功的记录（target_select judge=hit_volume）：')
    for l in b_new.logs:
        if l.kind == 'target_select' and l.detail.get('judge') == 'hit_volume':
            print(f'  帧 {l.frame}: {l.detail["unit"]} → {l.detail["target"]}'
                  f'  (hit_radius={l.detail["hit_radius"]})')

    print('\n★关键窗口几何（帧 405~440，芬 与 猎狗#2）：')
    fn = b_new.find_unit('芬')
    for s in b_new.frames:
        if not (405 <= s['f'] <= 440):
            continue
        row = [u for u in s['units'] if u['side'] == 'ENEMY' and u['key'] == 'enemy_1000_gopro']
        if not row:
            continue
        e = row[0]
        cells = b_new.cells_in_range(fn)
        dmin = min(b_new.point_to_cell_distance(e['x'], e['y'], c) for c in cells)
        import math
        dc = math.hypot(e['x'] - fn.pos_float()[0], e['y'] - fn.pos_float()[1])
        print(f'  帧 {s["f"]}: 敌 ({e["x"]:.2f},{e["y"]:.2f}) hp={e["hp"]} '
              f'格=({int(e["y"])},{int(e["x"])})  到芬中心 {dc:.2f}  到范围格 {dmin:.2f}')


if __name__ == '__main__':
    main()
