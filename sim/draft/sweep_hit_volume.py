# -*- coding: utf-8 -*-
"""sweep_hit_volume.py — ★扫描「受击判定体积」（敌人）以校准索敌语义

## 背景（用户 2026-09-15 明确）
索敌 = **方格范围** ∪ **受击判定体积**（体积**只用于索敌**，不用于 AoE 命中）。
本脚本扫描敌人的受击判定半径，找出与 1-1 标定最吻合的值。

★注意：这与早期"命中范围容差 `range_distance_tol=1.5`（中心距）"是**两种不同语义**：
  - 旧：`dist(目标中心, 自身中心) ≤ 1.5`
  - 新：`距离(目标中心, 范围格) ≤ hit_radius`
本脚本同时给出两版的对照，便于说明差异。

用法：
    python sweep_hit_volume.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

from ak_sim.engine import Battle              # noqa: E402
from ak_sim.events import extract_events      # noqa: E402
from ak_sim.scenario import Scenario          # noqa: E402
from replay_verify5 import MAP, DEPLOYS, DIR_MAP, to_rc   # noqa: E402


def run(options: dict) -> tuple[list[int], dict]:
    sc = Scenario('1-1')
    b = Battle(sc.stage_code, seed=0, record=True, record_every=1, max_frames=700,
               options=options)
    plan = {}
    for f, char, tile, direc, cov in DEPLOYS:
        plan.setdefault(f, []).append((char, to_rc(tile), direc, cov))
    for _ in range(700):
        b.tick()
        if b.frame in plan:
            for char, (r, c), direc, cov in plan[b.frame]:
                b.deploy(char, r, c, direction=DIR_MAP[direc], elite=2, level=90,
                         potential=6, trust=200, skill_index=0, skill_level=7, cost=cov)
    return b


def score(b: Battle) -> tuple[float, int, int, list[int]]:
    """用 replay_verify5 的人工对应表算偏差统计（沿用严格口径）。"""
    ev = extract_events(b.frames)
    order, n = {}, 0
    for e in sorted((x for x in ev if x['type'] == 'spawn'), key=lambda z: z['frame']):
        if str(e.get('name') or '') in ('芬', '月见夜', '令', '蕾缪安'):
            continue
        n += 1
        order[e.get('uid')] = n
    idx = {}
    for e in ev:
        t, uid = e['type'], e.get('uid')
        nm = str(e.get('name') or '')
        if t == 'spawn' and uid in order:
            idx.setdefault(('spawn', nm, '-'), []).append(e['frame'])
        elif t in ('damage', 'damage_first'):
            idx.setdefault(('dmg', nm, str(e.get('src') or '-')), []).append(e['frame'])
        elif t in ('despawn', 'kill') and uid in order:
            idx.setdefault(('kill', nm, '-'), []).append(e['frame'])
    for k in idx:
        idx[k] = sorted(set(idx[k]))
    diffs = []
    for f, _d, cat, vic, atk, i in MAP:
        if cat == 'watch':
            continue
        key = (cat, vic, atk) if cat == 'dmg' else (cat, vic, '-')
        fr = idx.get(key, [])
        if i < len(fr):
            diffs.append(abs(fr[i] - f))
    hit = sum(1 for d in diffs if d <= 6)
    return (sum(diffs) / max(1, len(diffs)), hit, max(diffs) if diffs else 0, diffs)


def main():
    print('=== ②受击判定体积（敌人）扫描：索敌 = 方格范围 ∪ 受击圆∩范围格 ===')
    print(f'{"hit_radius":>10} {"平均":>6} {"≤6帧":>5} {"最大":>5}  其余')
    for hr in (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0):
        b = run({'hit_volume_enemy': hr})
        avg, hit, mx, diffs = score(b)
        print(f'{hr:>10.2f} {avg:>6.2f} {hit:>5} {mx:>5}')
    print('\n=== 旧口径对照（中心距 ≤ N，语义混用版） ===')
    print(f'{"tol":>10} {"平均":>6} {"≤6帧":>5} {"最大":>5}')
    for tol in (1.0, 1.2, 1.5, 1.6, 1.8):
        b = run({'range_distance_tol': tol})
        avg, hit, mx, diffs = score(b)
        print(f'{tol:>10.2f} {avg:>6.2f} {hit:>5} {mx:>5}')
    print('\n=== 纯方格范围（无体积） ===')
    b = run({})
    avg, hit, mx, diffs = score(b)
    print(f'{"—":>10} {avg:>6.2f} {hit:>5} {mx:>5}')


if __name__ == '__main__':
    main()
