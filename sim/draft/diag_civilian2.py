# -*- coding: utf-8 -*-
"""diag_civilian2.py — 逐个平民：出生帧 / WAIT 总量 / 导航距离 / 实测到达帧 / 理论耗时。

若「实测到达」远大于「理论耗时」，说明我们的移动或检查点推进有问题（会连带推迟费用上限，
而首条弦惊 23 费 > 上限 20，必须靠平民 +2 抬升）。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

from ak_sim import fp                               # noqa: E402
from ak_sim import scenario_h124 as S               # noqa: E402
from ak_sim.engine import Battle, build_schedule    # noqa: E402

FPS = 30


def main():
    b = Battle(S.LEVEL, seed=0, record=False)
    routes = b.level.get('routes') or []
    spawns = [a for a in build_schedule(b.level) if a['type'] == 'SPAWN' and a['key'] == 'enemy_1313_wdfmr']
    print(f'平民 SPAWN {len(spawns)} 个')

    # 敌人数值（含 moveSpeed）
    for a in spawns[:6]:
        rt = routes[a['route']]
        sp, ep = rt['startPosition'], rt['endPosition']
        wait = sum(float(c.get('time') or 0) for c in (rt.get('checkpoints') or [])
                   if c.get('type') == 'WAIT_FOR_SECONDS')
        nm = b.map.build_navmap((int(ep['row']), int(ep['col'])))
        d = nm.get((int(sp['row']), int(sp['col'])))
        print(f'  t={a["t"]:6.1f}s route={a["route"]:>3} start({sp["row"]},{sp["col"]}) '
              f'→ end({ep["row"]},{ep["col"]}) WAIT={wait:.0f}s 导航距离={d:.2f}')

    # 实测
    b2 = Battle(S.LEVEL, seed=0, record=False)
    born, arrive = {}, {}
    orig_spawn, orig_ce = Battle._spawn_enemy, Battle._check_escape

    def sp(self, a):
        n0 = set(self.units)
        orig_spawn(self, a)
        new = set(self.units) - n0
        for uid in new:
            born[uid] = (self.frame, a['route'], self.units[uid].name)

    def ce(self, e):
        was = e.escaped
        orig_ce(self, e)
        if not was and e.escaped and e.uid in born and e.uid not in arrive:
            arrive[e.uid] = self.frame
    Battle._spawn_enemy, Battle._check_escape = sp, ce
    for _ in range(30 * 300):
        b2.tick()
    Battle._spawn_enemy, Battle._check_escape = orig_spawn, orig_ce

    print('\n=== 平民实测：出生 → 到达 ===')
    for uid in sorted(born):
        f0, ri, name = born[uid]
        fa = arrive.get(uid)
        rt = routes[ri]
        sp_, ep_ = rt['startPosition'], rt['endPosition']
        wait = sum(float(c.get('time') or 0) for c in (rt.get('checkpoints') or [])
                   if c.get('type') == 'WAIT_FOR_SECONDS')
        nm = b2.map.build_navmap((int(ep_['row']), int(ep_['col'])))
        d = nm.get((int(sp_['row']), int(sp_['col']))) or 0
        u = b2.units.get(uid)
        spd = (fp.to_float(u.move_speed) * b2.move_multiplier) if u else None
        theo = (d / spd + wait) if spd else None
        print(f'  uid={uid:>3} 出生 {f0/FPS:6.1f}s route={ri:>3} WAIT={wait:4.0f}s '
              f'距离={d:5.2f} 到达={("%.1fs" % (fa/FPS)) if fa else "未到达":>7} '
              f'实测耗时={("%.1fs" % ((fa-f0)/FPS)) if fa else "-":>7} '
              f'理论耗时={("%.1fs" % theo) if theo else "-":>7}')


if __name__ == '__main__':
    main()
