# -*- coding: utf-8 -*-
"""diag_flow_speed.py — 量化敌人「出生→进点」的实测耗时与理论耗时，定位流速偏差。

实机锚定测量（2026-09-14，演习、不部署任何干员、以费用数字当锚）：
  战斗 t=0 对应采样 11.5s；生命 3→2 在采样 55.6s ⇒ **首个漏怪 ≈ 44.3s**；
  第二只 ≈ 46.0s；判负 ≈ 51.5s。
模拟器同口径（有令+蕾缪安，二者均为高台不阻挡）：37.3 / 39.8 / 43.7s ⇒ 我方敌人**偏快约 19%**。
本脚本打印每只敌人的 出生帧 / 进点帧 / 实际行走路程（里程计）/ 名义速度，用来判断
是「速度常数偏大」还是「路径偏短」。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

from ak_sim import fp                               # noqa: E402
from ak_sim import scenario_h124 as S               # noqa: E402
from ak_sim.data import get_enemy                   # noqa: E402
from ak_sim.engine import Battle                    # noqa: E402

FPS = 30


def main():
    raw = get_enemy('enemy_1010_demon')
    attrs = raw.get('attrs') or raw
    print('萨卡兹大剑手(enemy_1010_demon) 原始数值:',
          {k: attrs.get(k) for k in ('maxHp', 'atk', 'def', 'moveSpeed', 'baseAttackTime')})

    b = Battle(S.LEVEL, seed=0, record=False)
    b.cost_max = 99.0
    b.cost = 99.0
    odo = {}
    last = {}
    born = {}
    esc = {}
    orig_spawn, orig_tick, orig_ce = Battle._spawn_enemy, Battle.tick, Battle._check_escape

    def sp(self, a):
        n0 = set(self.units)
        orig_spawn(self, a)
        for uid in set(self.units) - n0:
            born[uid] = (self.frame, a['key'], a['route'])
            u = self.units[uid]
            odo[uid] = 0.0
            last[uid] = (fp.to_float(u.pos[0]), fp.to_float(u.pos[1]))

    def tk(self):
        orig_tick(self)
        for uid, u in list(self.units.items()):
            if uid in odo and u.alive:
                x, y = fp.to_float(u.pos[0]), fp.to_float(u.pos[1])
                lx, ly = last[uid]
                odo[uid] += ((x - lx) ** 2 + (y - ly) ** 2) ** 0.5
                last[uid] = (x, y)

    def ce(self, e):
        was = e.escaped
        orig_ce(self, e)
        if not was and e.escaped and e.uid in born:
            esc[e.uid] = self.frame
    Battle._spawn_enemy, Battle.tick, Battle._check_escape = sp, tk, ce
    for _ in range(30 * 120):
        b.tick()
    Battle._spawn_enemy, Battle.tick, Battle._check_escape = orig_spawn, orig_tick, orig_ce

    print('\n=== 前 6 只进点的敌人 ===')
    print('  uid 名称                 出生   进点   耗时   里程   平均速度  名义速度')
    for uid in sorted(esc)[:6]:
        f0, key, ri = born[uid]
        f1 = esc[uid]
        dt = (f1 - f0) / FPS
        d = odo.get(uid, 0.0)
        u = b.units.get(uid)
        nom = None
        for x in b.logs:
            pass
        print(f'  {uid:>3} {key:<20} {f0/FPS:6.1f} {f1/FPS:6.1f} {dt:6.1f} {d:6.2f} '
              f'{d/dt:8.3f} 格/s')
    # 名义速度：取一只还在场的同类
    for u in b.units.values():
        if u.side == 'ENEMY' and u.key == 'enemy_1010_demon':
            print(f'\n  名义速度 = moveSpeed×moveMultiplier = '
                  f'{fp.to_float(u.move_speed):.3f}×{b.move_multiplier} = '
                  f'{fp.to_float(u.move_speed)*b.move_multiplier:.3f} 格/s')
            break


if __name__ == '__main__':
    main()
