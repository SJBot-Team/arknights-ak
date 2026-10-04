# -*- coding: utf-8 -*-
"""diag_move_probe.py — 在 _enemy_move 内部打点，看卡住的敌人到底拿到了什么。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

from ak_sim import fp                               # noqa: E402
from ak_sim import scenario_h124 as S               # noqa: E402
from ak_sim.engine import Battle                    # noqa: E402

FPS = 30
PROBE_FRAMES = (900, 901, 902)


def main():
    b = Battle(S.LEVEL, seed=0, record=False)
    orig = Battle._enemy_move
    logs = []

    def patched(self, e):
        cell = e.grid()
        before = (fp.to_float(e.pos[0]), fp.to_float(e.pos[1]))
        orig(self, e)
        after = (fp.to_float(e.pos[0]), fp.to_float(e.pos[1]))
        if self.frame in PROBE_FRAMES and cell == (2, 1):
            # 复算一遍内部量
            target_tile = e.route_end
            if e.checkpoints and e.checkpoint_idx < len(e.checkpoints):
                cp = e.checkpoints[e.checkpoint_idx]
                if isinstance(cp, dict) and str(cp.get('type', '')).upper() in ('MOVE', 'PATROL_MOVE'):
                    p = cp.get('position') or {}
                    target_tile = (int(p.get('row', 0)), int(p.get('col', 0)))
            nm = self.map.build_navmap(target_tile, flying=e.flying)
            nxt, snap = self.map.nav_step_target(cell, nm)
            logs.append((self.frame, e.uid, e.name, cell, round(before[0], 4), round(before[1], 4),
                         round(after[0], 4), round(after[1], 4), target_tile,
                         nm.get(cell), nxt, snap,
                         [((cell[0] + dr, cell[1] + dc), nm.get((cell[0] + dr, cell[1] + dc)))
                          for dr, dc in ((0, -1), (1, 0), (0, 1), (-1, 0))],
                         round(fp.to_float(e.inertia[0]), 4), round(fp.to_float(e.inertia[1]), 4),
                         e.state, e.wait_until))

    Battle._enemy_move = patched
    for _ in range(1200):
        b.tick()
    Battle._enemy_move = orig

    for row in logs[:14]:
        (f, uid, name, cell, bx, by, ax_, ay, tgt, dcur, nxt, snap, nbs, ivx, ivy, st, wu) = row
        print(f'f={f} uid={uid} {name} cell={cell} pos {bx},{by} → {ax_},{ay}')
        print(f'   target={tgt} dist(cell)={dcur} nxt={nxt} snap={snap} state={st} wait={wu} '
              f'v=({ivx},{ivy})')
        print(f'   邻格距离: {nbs}')


if __name__ == '__main__':
    main()
