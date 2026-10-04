# -*- coding: utf-8 -*-
"""diag_trace_enemy.py — 逐帧跟踪某个敌人，看它到底在干什么（位置/速度/目标/下一节点）。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

from ak_sim import fp                               # noqa: E402
from ak_sim import scenario_h124 as S               # noqa: E402
from ak_sim.engine import Battle                    # noqa: E402

FPS = 30
TARGET_GRID = (int(sys.argv[1]), int(sys.argv[2])) if len(sys.argv) > 2 else (2, 1)
F0, F1 = 880, 930


def main():
    b = Battle(S.LEVEL, seed=0, record=False)
    watch = []
    orig = Battle.tick

    def tick(self):
        orig(self)
        if F0 <= self.frame <= F1:
            for u in self.units.values():
                if u.side == 'ENEMY' and u.alive and u.grid() == TARGET_GRID:
                    watch.append((self.frame, u.uid, u.name, u.state,
                                  round(fp.to_float(u.pos[0]), 3), round(fp.to_float(u.pos[1]), 3),
                                  round(fp.to_float(u.inertia[0]), 3), round(fp.to_float(u.inertia[1]), 3),
                                  u.checkpoint_idx, len(u.checkpoints or []), u.route_end,
                                  u.route_index))

    Battle.tick = tick
    for _ in range(1200):
        b.tick()
    Battle.tick = orig
    print(f'帧 {F0}~{F1} 内位于 {TARGET_GRID} 的敌人轨迹（每 5 帧）')
    seen = set()
    for row in watch:
        f, uid = row[0], row[1]
        if f % 5:
            continue
        key = (uid, f)
        if key in seen:
            continue
        seen.add(key)
        print(f'  f={f:>4} uid={uid:>3} {row[2]:<12} {row[3]:<6} pos=({row[4]:.2f},{row[5]:.2f}) '
              f'v=({row[6]:+.2f},{row[7]:+.2f}) cp={row[8]}/{row[9]} end={row[10]} route={row[11]}')


if __name__ == '__main__':
    main()
