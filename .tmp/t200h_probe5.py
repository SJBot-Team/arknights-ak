# -*- coding: utf-8 -*-
"""T-200h 探针 5：打印参战单位的攻击间隔/前摇/（移动）参数。

只读运行模拟器。
"""
from __future__ import annotations
import os
import sys

sys.path.insert(0, r'C:\Users\23922\Documents\ds_harness\ak\sim\draft')
sys.stdout.reconfigure(encoding='utf-8')

from ak_sim.engine import Battle                      # noqa: E402
from ak_sim.scenario import Scenario                  # noqa: E402
from ak_sim import fp                                 # noqa: E402


def run(max_frames=60):
    sc = Scenario('1-1')
    b = Battle(sc.stage_code, seed=0, record=False, max_frames=max_frames)
    b.tick()
    b.deploy('char_123_fang', 3, 5, direction='左', elite=2, level=90, potential=6,
             trust=200, skill_index=0, skill_level=7, cost=8)
    for _ in range(max_frames - 1):
        b.tick()
    return b


def show(u, b, tag):
    ivf = getattr(u, 'attack_interval_fp', None)
    print(f'{tag:<12} key={u.key:<24} bat={fp.to_float(u.base_attack_time):.6f} '
          f'aspd={u.attack_speed} iv_frames={u.attack_interval_frames} '
          f'iv_fp={ivf} (={ivf/2**32:.6f}s)' if ivf else
          f'{tag} iv_fp=None')
    print(f'{"":<12} windup_frames={b._windup_frames(u)} src={getattr(u,"_windup_source",None)} '
          f'move_speed={fp.to_float(u.move_speed):.4f} '
          f'steer={getattr(u,"steering_factor",None)} maxSteer={getattr(u,"max_steering_force",None)}')


if __name__ == '__main__':
    b = run()
    for u in sorted(b.units.values(), key=lambda z: z.uid):
        show(u, b, 'ALLY' if u.is_operator else 'ENEMY')
