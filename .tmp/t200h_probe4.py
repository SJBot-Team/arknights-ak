# -*- coding: utf-8 -*-
"""T-200h 探针 4：量测"进入攻击范围/阻挡半径"的帧与位置（看移动链是否偏早）。

只读运行模拟器。
"""
from __future__ import annotations
import math
import os
import sys

sys.path.insert(0, r'C:\Users\23922\Documents\ds_harness\ak\sim\draft')
sys.stdout.reconfigure(encoding='utf-8')

from ak_sim.engine import Battle                      # noqa: E402
from ak_sim.scenario import Scenario                  # noqa: E402


def run(max_frames=520, off=0):
    os.environ['AK_SIM_SCHED_OFFSET_FRAMES'] = str(off)
    import importlib
    import ak_sim.engine as E
    importlib.reload(E)
    sc = Scenario('1-1')
    b = E.Battle(sc.stage_code, seed=0, record=True, record_every=1,
                 max_frames=max_frames)
    b.tick()
    b.deploy('char_123_fang', 3, 5, direction='左', elite=2, level=90, potential=6,
             trust=200, skill_index=0, skill_level=7, cost=8)
    for _ in range(max_frames - 1):
        b.tick()
    return b


if __name__ == '__main__':
    b = run()
    fang = None
    for u in b.units.values():
        if u.key == 'char_123_fang':
            fang = u
    fx, fy = fang.pos[0] / 4294967296.0, fang.pos[1] / 4294967296.0
    print(f'芬 中心 = ({fx:.4f},{fy:.4f}) grid={fang.grid()}')
    dog_rows = []
    for fr in b.frames:
        for u in fr['units']:
            if (u['key'] or '') != 'enemy_1000_gopro_2':
                continue
            d = math.hypot(u['x'] - fx, u['y'] - fy)
            dog_rows.append((fr['f'], u['x'], u['y'], d, u['v_abs'], u['state'],
                             u['blocked']))
    first_targetable = None
    for fr in b.frames:
        for l in (fr.get('ops') or []):
            pass
    for f, x, y, d, v, st, bl in dog_rows:
        mark = ''
        if d <= 0.7071 and not mark:
            mark += ' ★进入阻挡半径'
        if f <= 210 or (225 <= f <= 240) or (d <= 0.9 and len(mark)):
            print(f'  f={f:>4} x={x:.4f} y={y:.4f} dist={d:.4f} |v|={v:.4f} {st} blocked={bl}{mark}')
        if d <= 0.7071:
            break
    # 打印 芬 首次 target_select 的帧
    for l in b.logs:
        if l.kind == 'target_select' and (l.detail or {}).get('unit') == '芬':
            print(f'  芬 首次 target_select @ f={l.frame} {l.detail}')
            break
    # 打印 block 事件
    for l in b.logs:
        if l.kind == 'block':
            print(f'  block @ f={l.frame} {l.detail}')
