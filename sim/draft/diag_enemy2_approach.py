# -*- coding: utf-8 -*-
"""diag_enemy2_approach.py — 追踪 1-1 第 2 只敌人（猎狗, route4）的接近过程，
定位"芬为何比标定晚 18 帧才能索敌"。

标定事实（1-1 表）：
- 帧 367「猎狗 出现影子」（≈ spawn 360）
- 帧 **432「芬 命中猎狗」** ⇒ 按芬前摇 18 帧 ⇒ **索敌（起前摇）应在帧 414**
- 帧 443「芬 阻挡猎狗」

用户 2026-09-15 明确：**无阻挡时，敌人的 0.1 圆进入芬的 2 个方格** ⇒ 芬索敌并起前摇。
本脚本逐帧打印第 2 只的位置/格/到范围格距离/状态，找出它**何时首次满足该条件**。
"""
from __future__ import annotations

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

from ak_sim import data as D                 # noqa: E402
from ak_sim.engine import Battle             # noqa: E402
from ak_sim.scenario import Scenario         # noqa: E402
from replay_verify5 import DEPLOYS, DIR_MAP, to_rc   # noqa: E402

FRAMES = 520


def main():
    sc = Scenario('1-1')
    lv = D.load_level(sc.stage_code)
    routes = lv.get('routes') or []
    print('★ route4（第 2 只猎狗）原始定义：')
    import json
    print(json.dumps(routes[4], ensure_ascii=False)[:900])
    print()

    b = Battle(sc.stage_code, seed=0, record=True, record_every=1, max_frames=FRAMES,
               options={'hit_volume_enemy': 0.1})
    plan = {}
    for f, char, tile, direc, cov in DEPLOYS:
        plan.setdefault(f, []).append((char, to_rc(tile), direc, cov))
    for _ in range(FRAMES):
        b.tick()
        if b.frame in plan:
            for char, (r, c), direc, cov in plan[b.frame]:
                b.deploy(char, r, c, direction=DIR_MAP[direc], elite=2, level=90,
                         potential=6, trust=200, skill_index=0, skill_level=7, cost=cov)

    fn = b.find_unit('芬')
    cells = b.cells_in_range(fn)
    fcx = fn.pos[0] / (1 << 32)
    fcy = fn.pos[1] / (1 << 32)
    print(f'芬 位置 ({fcx:.2f},{fcy:.2f})  格 {fn.grid()}  范围格 {sorted(cells)}'
          f'  受击半径 {fn.hit_radius}\n')
    print(f'{"帧":>5} {"敌x":>6} {"敌y":>6} {"格":>8} {"状态":>8} {"到范围格":>9} '
          f'{"到芬":>6} {"hp":>5}  备注')

    uid2 = next(s['uid'] for e in b.logs if e.kind == 'spawn' and e.detail.get('key') == 'enemy_1000_gopro'
                for s in [{'uid': e.detail.get('uid', 3)}])
    first_ok = None
    for s in b.frames:
        if not (355 <= s['f'] <= 470):
            continue
        e = next((u for u in s['units'] if u['side'] == 'ENEMY'
                  and u['key'] == 'enemy_1000_gopro'), None)
        if e is None:
            continue
        dmin = min(b.point_to_cell_distance(e['x'], e['y'], c) for c in cells)
        dc = math.hypot(e['x'] - fcx, e['y'] - fcy)
        ok = dmin <= float(e.get('hit_radius') or 0.1)
        if ok and first_ok is None:
            first_ok = s['f']
        note = ''
        if s['f'] % 30 == 0:
            note = '  ← 整秒'
        print(f'{s["f"]:>5} {e["x"]:>6.2f} {e["y"]:>6.2f} '
              f'{str((int(e["y"]), int(e["x"]))):>8} {e["state"]:>8} {dmin:>9.2f} '
              f'{dc:>6.2f} {e["hp"]:>5} {note}{"  ★首次满足索敌条件" if s["f"] == first_ok else ""}')

    print(f'\n★模拟器首次满足「0.1 圆进入芬的 2 格」= 帧 **{first_ok}**')
    print(f'★按芬前摇 {b._windup_frames(fn)} 帧 ⇒ 首次命中 = 帧 {first_ok + b._windup_frames(fn) if first_ok else None}')
    print('★标定：索敌应在帧 **414**、命中帧 **432**')
    if first_ok:
        print(f'⇒ 模拟器比标定**晚 {first_ok - 414} 帧**进入可索敌状态 '
              f'（敌人速度 {1.9}格/s ⇒ 约 {(first_ok - 414) * 1.9 / 30:.2f} 格行程）')


if __name__ == '__main__':
    main()
