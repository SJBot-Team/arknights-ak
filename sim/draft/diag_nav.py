# -*- coding: utf-8 -*-
"""diag_nav.py — 直接检查某个敌人当前格的导航距离场，看它为什么不动。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

from ak_sim import scenario_h124 as S            # noqa: E402
from ak_sim.engine import Battle                  # noqa: E402

FPS = 30


def main():
    b = Battle(S.LEVEL, seed=0, record=False)
    m = b.map
    # 推进 900 帧（不跑轴，纯看敌人自己走）
    for _ in range(900):
        b.tick()
    stuck = [u for u in b.units.values() if u.side == 'ENEMY' and u.alive]
    stuck.sort(key=lambda u: u.created_frame)
    print(f'900 帧后存活 {len(stuck)} 只')
    for e in stuck[:4]:
        print(f'\n--- {e.name} uid={e.uid} grid={e.grid()} pos={e.world_xy()} '
              f'checkpoint {e.checkpoint_idx}/{len(e.checkpoints or [])} end={e.route_end} '
              f'flying={e.flying} move_speed={e.move_speed/FPS:.2f}格/秒')
        for tgt, tag in ((e.route_end, 'route_end'),):
            nm = m.build_navmap(tgt, flying=e.flying)
            r, c = e.grid()
            print(f'  navmap→{tag}{tgt}: size={len(nm)}  dist@({r},{c})={nm.get((r,c))}')
            for dr, dc in ((0, -1), (1, 0), (0, 1), (-1, 0)):
                nr, nc = r + dr, c + dc
                t = m.tile(nr, nc)
                print(f'    ({nr},{nc}) {t.key if t else "OOB"}/'
                      f'{"H" if t and t.height_type=="HIGHLAND" else "L"}/'
                      f'gpass={m.is_passable(nr,nc,e.flying)} '
                      f'door={(nr,nc) in m.door_tiles} dev={(nr,nc) in m.device_blocked} '
                      f'dist={nm.get((nr,nc))}')
        print(f'  next_node={m.next_node(e.pos, m.build_navmap(e.route_end, flying=e.flying))}')


if __name__ == '__main__':
    main()
