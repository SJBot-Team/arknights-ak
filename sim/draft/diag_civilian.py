# -*- coding: utf-8 -*-
"""diag_civilian.py — 平民（诺伯特平民）路线与到达时间：核对 +2 费用上限的到账时点。

需求背景：h12-4 首条弦惊在 **29.0s** 落地（作者作战记录 r7），而弦惊要 23 费、
关卡 rune 把上限压到 20 ⇒ 29s 之前**必须有东西把上限抬到 ≥23**：
  · 打掉「街头应急储备」+5/+5（2 个）
  · 平民到达路径终点 +2（每个）
本脚本回答：我们模拟里这些 +上限 事件的到达时刻是否与 29s 相容。
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
    spawns = [a for a in build_schedule(b.level) if a['type'] == 'SPAWN']

    # 平民 = enemy_1313_wdfmr
    civ_routes = sorted({a['route'] for a in spawns if a['key'] == 'enemy_1313_wdfmr'})
    print(f'平民使用路线 {civ_routes}')
    for ri in civ_routes:
        rt = routes[ri]
        sp = rt.get('startPosition') or {}
        ep = rt.get('endPosition') or {}
        cps = [(c.get('type'), c.get('time'), (c.get('position') or {}).get('row'),
                (c.get('position') or {}).get('col')) for c in (rt.get('checkpoints') or [])]
        print(f'  route {ri}: start({sp.get("row")},{sp.get("col")}) → end({ep.get("row")},{ep.get("col")})')
        print(f'     检查点: {cps}')
        # 导航距离
        try:
            nm = b.map.build_navmap((int(ep['row']), int(ep['col'])))
            d = nm.get((int(sp['row']), int(sp['col'])))
            print(f'     起点→终点导航距离 = {d}')
        except Exception as e:
            print('     navmap 失败', e)

    # 实测到达时刻
    b2 = Battle(S.LEVEL, seed=0, record=False)
    arrive = []
    orig = Battle.tick
    seen = set()

    def tk(self):
        orig(self)
        for l in self.logs[-50:]:
            if l.kind == 'civilian_arrived' and l.frame not in seen:
                seen.add(l.frame)
                arrive.append((l.frame, l.detail))
    Battle.tick = tk
    for _ in range(30 * 200):
        b2.tick()
    Battle.tick = orig
    print(f'\n=== 实测平民到达（+2 上限）共 {len(arrive)} 次 ===')
    for f, d in arrive[:20]:
        print(f'  {f:>5}f {f/FPS:6.1f}s  {d}')

    print('\n=== 上限抬升时间线（模拟）===')
    b3 = Battle(S.LEVEL, seed=0, record=False)
    orig3 = Battle.add_cost_cap
    ups = []

    def acp(self, delta):
        orig3(self, delta)
        ups.append((self.frame, delta, self.cost_max))
    Battle.add_cost_cap = acp
    for _ in range(30 * 200):
        b3.tick()
    Battle.add_cost_cap = orig3
    for f, d, cm in ups[:20]:
        print(f'  {f:>5}f {f/FPS:6.1f}s  +{d:.0f} → 上限 {cm:.0f}')


if __name__ == '__main__':
    main()
